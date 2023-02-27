import json
import math
import os
import random
import sys
from collections import defaultdict


def split(fn):
    with open(fn) as f:
        smpl_packs = json.load(f)

    dev_size_min_smpls = 1000
    test_size_min_smpls = 1000
    splits = ['test', 'dev', 'train']  # in fill order

    # determine sample and label key
    for key in ['imrad_smpls', 'citrec_smpls']:
        if key in smpl_packs[0]:
            sample_key = key

    # calculate sample allocation goals
    dists_abs = {}
    dev_fill_min = {}
    test_fill_min = {}
    dev_fill_curr = {}
    test_fill_curr = {}
    strat_dimensions = ['year', 'discipline', 'label']
    num_packets_for_label = defaultdict(int)
    for strat in strat_dimensions:
        dists_abs[strat] = defaultdict(int)
        dev_fill_min[strat] = defaultdict(int)
        test_fill_min[strat] = defaultdict(int)
        dev_fill_curr[strat] = defaultdict(int)
        test_fill_curr[strat] = defaultdict(int)
    # # determine usable labels
    for ppr in smpl_packs:
        uniq_lbls = set()
        for smpl in ppr[sample_key]:
            uniq_lbls.add(smpl['label'])
        for lbl in uniq_lbls:
            num_packets_for_label[lbl] += 1
    usable_labels = [
        k for (k, v) in num_packets_for_label.items()
        if v >= len(splits)
    ]
    # # filter samples to only contain usable labels
    smpl_packs_usable = []
    for ppr in smpl_packs:
        smpls_usable = []
        for smpl in ppr[sample_key]:
            if smpl['label'] in usable_labels:
                smpls_usable.append(smpl)
        if len(smpls_usable) > 0:
            ppr_usable = {}
            for k, v in ppr.items():
                if k != sample_key:
                    ppr_usable[k] = v
            ppr_usable[sample_key] = smpls_usable
            smpl_packs_usable.append(ppr_usable)
    smpl_packs = smpl_packs_usable
    # # determine total distribution of stratification dimensions
    for ppr in smpl_packs:
        dists_abs['year'][ppr['year']] += len(ppr[sample_key])
        dists_abs['discipline'][ppr['discipline']] += len(ppr[sample_key])
        for smpl in ppr[sample_key]:
            dists_abs['label'][smpl['label']] += 1
    # # determine relative distribution of stratification dimensions
    # # and calculate allocation minima
    smpls_total = sum(n for n in dists_abs['year'].values())
    for strat in strat_dimensions:
        for k, v in dists_abs[strat].items():
            rel_size = v / smpls_total
            dev_fill_min[strat][k] = math.ceil(
                dev_size_min_smpls * rel_size
            )
            test_fill_min[strat][k] = math.ceil(
                test_size_min_smpls * rel_size
            )
    # allocate samples
    smpls_split = {}
    for split in splits:
        smpls_split[split] = []
    split_mins = {
        'test': test_fill_min,
        'dev': dev_fill_min,
    }
    split_currs = {
        'test': test_fill_curr,
        'dev': dev_fill_curr,
    }
    random.seed(42)
    random.shuffle(smpl_packs)
    for ppr in smpl_packs:
        added = False
        for i, split in enumerate(splits[:-1]):  # put in test or dev
            # check if labels to be allocated have enough remaining samples
            num_other_splits = len(splits) - i - 1
            cant_use = False
            for smpl in ppr[sample_key]:
                if num_packets_for_label[smpl['label']] <= num_other_splits:
                    cant_use = True
                    break
            if cant_use:
                continue
            # check if current paper samples are useful to add to split
            num_strat_dims_needed = 0
            for strat in strat_dimensions:  # for all dims
                needed = False
                for k in dists_abs[strat].keys():  # for all vals
                    n_curr = split_currs[split][strat][k]
                    n_min = split_mins[split][strat][k]
                    if n_curr < n_min:
                        needed = True
                        break
                if needed:
                    num_strat_dims_needed += 1
            # add if useful
            if num_strat_dims_needed == len(strat_dimensions):
                smpls_split[split].extend(
                    remove_debug_fields(ppr[sample_key])
                )
                added = True
                # keep track of allocation numbers
                split_currs[split]['year'][ppr['year']] += len(
                    ppr[sample_key]
                )
                split_currs[split]['discipline'][ppr['discipline']] += len(
                    ppr[sample_key]
                )
                for smpl in ppr[sample_key]:
                    split_currs[split]['label'][smpl['label']] += 1
                # keep track of packets left per label
                for lbl in set([s['label'] for s in ppr[sample_key]]):
                    num_packets_for_label[lbl] -= 1
                # don’t add to other splits
                break
        # add to train if “not needed” in tran/dev
        if not added:
            smpls_split['train'].extend(
                remove_debug_fields(ppr[sample_key])
            )

    # for split in splits[:-1]:
    #     print(split)
    #     split_total = len(smpls_split[split])
    #     print(f'\tsamples total: {split_total}')
    #     for strat in strat_dimensions:
    #         for k in dists_abs[strat].keys():
    #             rel_of_total = dists_abs[strat][k] / smpls_total
    #             rel_of_split = split_currs[split][strat][k] / split_total
    #             print((
    #                 f'\t\t{strat}-{k}: {rel_of_total:.4f} '
    #                 f'-> {rel_of_split:.4f}'
    #                 f' ({split_currs[split][strat][k]})'
    #             ))
    #             input()

    fn_base, ext = os.path.splitext(os.path.split(fn)[-1])
    for split, smpls in smpls_split.items():
        fn = f'{fn_base}_{split}.jsonl'
        with open(fn, 'w') as f:
            for smpl in smpls:
                f.write(json.dumps(smpl) + '\n')


def remove_debug_fields(smpls):
    """ Remove dict fields starting with _
    """

    clean_smpls = []
    for smpl in smpls:
        clean_smpls.append(
            {
                k: v for (k, v)
                in smpl.items()
                if k[0] != '_'
            }
        )
    return clean_smpls


if __name__ == '__main__':
    split(sys.argv[1])
