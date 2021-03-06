#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import itertools

import reader
import paddle.v2 as paddle
from network_conf import DSSM
from utils import logger, ModelType, ModelArch, load_dic

parser = argparse.ArgumentParser(description="PaddlePaddle DSSM infer")
parser.add_argument(
    '--model_path',
    type=str,
    required=True,
    help="path of model parameters file")
parser.add_argument(
    '-i',
    '--data_path',
    type=str,
    required=True,
    help="path of the dataset to infer")
parser.add_argument(
    '-o',
    '--prediction_output_path',
    type=str,
    required=True,
    help="path to output the prediction")
parser.add_argument(
    '-y',
    '--model_type',
    type=int,
    required=True,
    default=ModelType.CLASSIFICATION_MODE,
    help="model type, %d for classification, %d for pairwise rank, %d for regression (default: classification)"
    % (ModelType.CLASSIFICATION_MODE, ModelType.RANK_MODE,
       ModelType.REGRESSION_MODE))
parser.add_argument(
    '-s',
    '--source_dic_path',
    type=str,
    required=False,
    help="path of the source's word dic")
parser.add_argument(
    '--target_dic_path',
    type=str,
    required=False,
    help="path of the target's word dic, if not set, the `source_dic_path` will be used"
)
parser.add_argument(
    '-a',
    '--model_arch',
    type=int,
    required=True,
    default=ModelArch.CNN_MODE,
    help="model architecture, %d for CNN, %d for FC, %d for RNN" %
    (ModelArch.CNN_MODE, ModelArch.FC_MODE, ModelArch.RNN_MODE))
parser.add_argument(
    '--share_network_between_source_target',
    type=bool,
    default=False,
    help="whether to share network parameters between source and target")
parser.add_argument(
    '--share_embed',
    type=bool,
    default=False,
    help="whether to share word embedding between source and target")
parser.add_argument(
    '--dnn_dims',
    type=str,
    default='256,128,64,32',
    help="dimentions of dnn layers, default is '256,128,64,32', which means create a 4-layer dnn, demention of each layer is 256, 128, 64 and 32"
)
parser.add_argument(
    '-c',
    '--class_num',
    type=int,
    default=0,
    help="number of categories for classification task.")

args = parser.parse_args()
args.model_type = ModelType(args.model_type)
args.model_arch = ModelArch(args.model_arch)
if args.model_type.is_classification():
    assert args.class_num > 1, "--class_num should be set in classification task."

layer_dims = map(int, args.dnn_dims.split(','))
args.target_dic_path = args.source_dic_path if not args.target_dic_path else args.target_dic_path

paddle.init(use_gpu=False, trainer_count=1)


class Inferer(object):
    def __init__(self, param_path):
        logger.info("create DSSM model")

        cost, prediction, label = DSSM(
            dnn_dims=layer_dims,
            vocab_sizes=[
                len(load_dic(path))
                for path in [args.source_dic_path, args.target_dic_path]
            ],
            model_type=args.model_type,
            model_arch=args.model_arch,
            share_semantic_generator=args.share_network_between_source_target,
            class_num=args.class_num,
            share_embed=args.share_embed)()

        # load parameter
        logger.info("load model parameters from %s" % param_path)
        self.parameters = paddle.parameters.Parameters.from_tar(
            open(param_path, 'r'))
        self.inferer = paddle.inference.Inference(
            output_layer=prediction, parameters=self.parameters)

    def infer(self, data_path):
        logger.info("infer data...")
        dataset = reader.Dataset(
            train_path=data_path,
            test_path=None,
            source_dic_path=args.source_dic_path,
            target_dic_path=args.target_dic_path,
            model_type=args.model_type, )
        infer_reader = paddle.batch(dataset.infer, batch_size=1000)
        logger.warning('write predictions to %s' % args.prediction_output_path)

        output_f = open(args.prediction_output_path, 'w')

        for id, batch in enumerate(infer_reader()):
            res = self.inferer.infer(input=batch)
            predictions = [' '.join(map(str, x)) for x in res]
            assert len(batch) == len(
                predictions), "predict error, %d inputs, but %d predictions" % (
                    len(batch), len(predictions))
            output_f.write('\n'.join(map(str, predictions)) + '\n')


if __name__ == '__main__':
    inferer = Inferer(args.model_path)
    inferer.infer(args.data_path)
