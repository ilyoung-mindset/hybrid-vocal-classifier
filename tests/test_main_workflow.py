"""
tests running a 'typical' workflow
all thrown into one file
because the tests have to run in a certain order
and this seemed like the easiest, least fragile way to do taht
"""

import os
import glob

import pytest
import numpy as np
from sklearn.externals import joblib

import hvc

configs = './test_data/config.yaml/'


@pytest.fixture(scope='session')
def tmp_output_dir(tmpdir_factory):
    fn = tmpdir_factory.mktemp('tmp_output_dir')
    return fn


@pytest.fixture(scope='session')
def tmp_config_dir(tmpdir_factory):
    fn = tmpdir_factory.mktemp('tmp_config_dir')
    return fn


#########################
#   utility functions   #
#########################
def rewrite_config(config_dir,
                   replace_dict,
                   config_filename):
    """rewrites config files,
    e.g. to insert name of temporary directories

    config_dir : directory where config file gets saved
    replace_dict : dict
        keys are strings to search for
        values are 2-element tuples
            element 1: another string to search for
            element 2: string put in place of element 1
        used to find keys and values in config dicts
        i.e. first match key from replace_dict with key in config_dict,
        then replace val in config dict (element 1) with actual val (element 2)
        element 2 will be the name of the temporary directory generated by pytest
    """

    config_file_path = os.path.join(configs, config_filename)

    # find key in config dict and replace value for that key
    with open(config_file_path) as config_file:
        config_as_list = config_file.readlines()
    for key, val_tuple in replace_dict.items():
        for ind, line in enumerate(config_as_list):
            if key in line:
                config_as_list[ind] = config_as_list[ind].replace(
                    val_tuple[0],
                    val_tuple[1]
                )

    # write to file in temporary configs dir
    tmp_config_path = os.path.join(str(config_dir), config_filename)
    with open(tmp_config_path, 'w') as tmp_config_file:
        tmp_config_file.writelines(config_as_list)
    # return location of that file
    return tmp_config_path


def check_extract_output(output_dir):
    """
    """

    ftr_files = glob.glob(os.path.join(output_dir, 'features_from*'))
    ftr_dicts = []
    for ftr_file in ftr_files:
        ftr_dicts.append(joblib.load(ftr_file))

    # if features were extracted (not spectrograms)
    if any(['features' in ftr_dict for ftr_dict in ftr_dicts]):
        # then all ftr_dicts should have `features` key
        assert all(['features' in ftr_dict for ftr_dict in ftr_dicts])
        # and the number of rows in features should equal number of labels
        for ftr_dict in ftr_dicts:
            labels = ftr_dict['labels']
            features = ftr_dict['features']
            assert features.shape[0] == len(labels)

        # make sure number of features i.e. columns is constant across feature matrices
        ftr_cols = [ftr_dict['features'].shape[1] for ftr_dict in ftr_dicts]
        assert np.unique(ftr_cols).shape[-1] == 1

    # if features are spectrograms for neural net
    if any(['neuralnets_input_dict' in ftr_dict for ftr_dict in ftr_dicts]):
        # then all feature dicts should have spectrograms
        assert all(['neuralnets_input_dict' in ftr_dict for ftr_dict in ftr_dicts])
        neuralnet_keys = [ftr_dict['neuralnets_input_dict'].keys()
                          for ftr_dict in ftr_dicts]
        # make sure keys are all the same for neuralnets_input_dict from every ftr_dict
        for ind, keyset in enumerate(neuralnet_keys):
            other_keysets = neuralnet_keys[:ind] + neuralnet_keys[(ind+1):]
            assert keyset.difference(other_keysets) == set()
        # if they are all the same, then save that set of keys
        # to compare with summary feature dict below
        neuralnet_keys = neuralnet_keys[0]

        for ftr_dict in ftr_dicts:
            labels = ftr_dict['labels']
            for key, val in ftr_dict['neuralnet_inputs_dict']:
                assert val.shape[0] == len(labels)

    # make sure rows in summary dict features == sum of rows of each ftr file features
    summary_file = glob.glob(os.path.join(output_dir, 'summary_feature_file_*'))
    # (should only be one summary file)
    assert len(summary_file) == 1
    summary_dict = joblib.load(summary_file[0])
    if all(['features' in ftr_dict for ftr_dict in ftr_dicts]):
        sum_ftr_rows = summary_dict['features'].shape[0]
        total_ftr_dict_rows = sum([ftr_dict['features'].shape[0]
                                   for ftr_dict in ftr_dicts])
        assert sum_ftr_rows == total_ftr_dict_rows

    if all(['neuralnets_input_dict' in ftr_dict for ftr_dict in ftr_dicts]):
        assert summary_dict['neuralnet_inputs_dict'].keys() == neuralnet_keys
        for key, val in summary_dict['neuralnet_inputs_dict']:
            sum_ftr_rows = summary_dict['neuralnets_input_dict'][key].shape[0]
            total_ftr_dict_rows = sum(
                [ftr_dict['neuralnet_inputs_dict'][key].shape[0]
                 for ftr_dict in ftr_dicts])
            assert sum_ftr_rows == total_ftr_dict_rows

    return True  # because called with assert


def check_select_output(config_path, output_dir):
    """
    """

    select_output = glob.glob(os.path.join(str(output_dir),
                                            'summary_model_select_file*'))
    # should only be one summary output file
    assert len(select_output) == 1

    # now check for every model in config
    # if there is corresponding folder with model files etc
    select_config = hvc.parse_config(config_path, 'select')
    select_model_dirs = next(
        os.walk(
            output_dir)
    )[1]  # [1] to return just dir names
    select_model_folder_names = [hvc.modelselect.determine_model_output_folder_name(
        model_dict) for model_dict in select_config['models']]
    for folder_name in select_model_folder_names:
        assert folder_name in select_model_dirs

    return True


test_config_tuples = [
    ('test_extract_knn.config.yml',
     ['test_select_knn_ftr_list_inds.config.yml',
      'test_select_knn_ftr_grp.config.yml']
     ),
    ('test_extract_multiple_feature_groups.config.yml',
     ['test_select_multiple_ftr_grp.config.yml']
     ),
    ('test_extract_svm.config.yml',
     ['test_select_svm.config.yml']
     ),
    ('test_extract_flatwindow.config.yml',
     ['test_select_flatwindow.config.yml']
     )
]


#########################
#     actual tests      #
#########################
def test_main_workflow(tmp_config_dir, tmp_output_dir):
    """
    """

    for test_config_tuple in test_config_tuples:

        extract_config_filename = test_config_tuple[0]
        # have to put tmp_output_dir into yaml file
        tmp_config_path = rewrite_config(tmp_config_dir,
                                         replace_dict={'output_dir':
                                                           ('replace with tmp_output_dir',
                                                            str(tmp_output_dir))},
                                         config_filename=extract_config_filename)
        hvc.extract(tmp_config_path)
        extract_outputs = list(
            filter(os.path.isdir, glob.glob(os.path.join(
                str(tmp_output_dir),
                '*extract*'))
                   )
        )
        extract_outputs.sort(key=os.path.getmtime)
        extract_output_dir = (extract_outputs[-1])  # [-1] is newest dir, after sort
        assert check_extract_output(extract_output_dir)

        feature_file = glob.glob(os.path.join(extract_output_dir, 'summary*'))
        feature_file = feature_file[0]  # because glob returns list

        select_config_filenames = test_config_tuple[1]

        while True:
            try:
                select_config_filename = select_config_filenames.pop()
                tmp_config_path = rewrite_config(tmp_config_dir,
                                                 replace_dict={'feature_file':
                                                                   ('replace with feature_file',
                                                                    feature_file),
                                                               'output_dir':
                                                                   ('replace with tmp_output_dir',
                                                                    str(tmp_output_dir))},
                                                 config_filename=select_config_filename)
                hvc.select(tmp_config_path)
                select_outputs = list(
                    filter(os.path.isdir, glob.glob(os.path.join(
                        str(tmp_output_dir),
                        '*select*'))
                           )
                )
                select_outputs.sort(key=os.path.getmtime)
                select_output_dir = (select_outputs[-1])  # [-1] is newest dir, after sort
                assert check_select_output(tmp_config_path, select_output_dir)
            except IndexError:  # because pop from empty list
                break

