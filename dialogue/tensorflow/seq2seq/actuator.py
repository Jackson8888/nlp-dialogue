# Copyright 2021 DengBoCong. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""seq2seq结构的实现执行器入口
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import json
import tensorflow as tf
from argparse import ArgumentParser
from typing import NoReturn
import dialogue.tensorflow.seq2seq.model as seq2seq
from dialogue.preprocess_corpus import preprocess_dataset
from dialogue.preprocess_corpus import to_single_turn_dataset
from dialogue.tensorflow.seq2seq.modules import Seq2SeqModule
from dialogue.tensorflow.utils import load_checkpoint
from dialogue.tools import load_tokenizer
from dialogue.tools import show_history


def tf_seq2seq() -> NoReturn:
    parser = ArgumentParser(description="seq2seq chatbot")
    parser.add_argument("--version", default="tf", type=str, required=True, help="执行版本")
    parser.add_argument("--model", default="transformer", type=str, required=True, help="执行模型")
    parser.add_argument("--config_file", default="", type=str, required=False, help="配置文件路径，为空则默认命令行，不为空则使用配置文件参数")
    parser.add_argument("--act", default="pre_treat", type=str, required=False, help="执行类型")
    parser.add_argument("--cell_type", default="lstm", type=str, required=False, help="rnn的cell类型")
    parser.add_argument("--if_bidirectional", default=True, type=bool, required=False, help="是否开启双向rnn")
    parser.add_argument("--units", default=1024, type=int, required=False, help="隐藏层单元数")
    parser.add_argument("--vocab_size", default=20000, type=int, required=False, help="词汇大小")
    parser.add_argument("--embedding_dim", default=512, type=int, required=False, help="嵌入层维度大小")
    parser.add_argument("--encoder_layers", default=6, type=int, required=False, help="encoder的层数")
    parser.add_argument("--decoder_layers", default=6, type=int, required=False, help="decoder的层数")
    parser.add_argument("--max_train_data_size", default=0, type=int, required=False, help="用于训练的最大数据大小")
    parser.add_argument("--max_valid_data_size", default=0, type=int, required=False, help="用于验证的最大数据大小")
    parser.add_argument("--max_sentence", default=40, type=int, required=False, help="单个序列的最大长度")
    parser.add_argument("--dict_path", default="data\\preprocess\\seq2seq_dict.json",
                        type=str, required=False, help="字典路径")
    parser.add_argument("--checkpoint_dir", default="checkpoints\\tensorflow\\seq2seq",
                        type=str, required=False, help="检查点路径")
    parser.add_argument("--resource_data_path", default="data\\LCCC.json", type=str, required=False, help="原始数据集路径")
    parser.add_argument("--tokenized_data_path", default="data\\preprocess\\lccc_tokenized.txt",
                        type=str, required=False, help="处理好的多轮分词数据集路径")
    parser.add_argument("--preprocess_data_path", default="data\\preprocess\\single_tokenized.txt",
                        type=str, required=False, help="处理好的单轮分词数据集路径")
    parser.add_argument("--valid_data_path", default="data\\preprocess\\single_tokenized.txt", type=str,
                        required=False, help="处理好的单轮分词验证评估用数据集路径")
    parser.add_argument("--history_image_dir", default="data\\history\\seq2seq\\", type=str, required=False,
                        help="数据指标图表保存路径")
    parser.add_argument("--valid_freq", default=5, type=int, required=False, help="验证频率")
    parser.add_argument("--checkpoint_save_freq", default=2, type=int, required=False, help="检查点保存频率")
    parser.add_argument("--checkpoint_save_size", default=1, type=int, required=False, help="单轮训练中检查点保存数量")
    parser.add_argument("--batch_size", default=64, type=int, required=False, help="batch大小")
    parser.add_argument("--buffer_size", default=20000, type=int, required=False, help="Dataset加载缓冲大小")
    parser.add_argument("--beam_size", default=3, type=int, required=False, help="BeamSearch的beam大小")
    parser.add_argument("--valid_data_split", default=0.2, type=float, required=False, help="从训练数据集中划分验证数据的比例")
    parser.add_argument("--epochs", default=5, type=int, required=False, help="训练步数")
    parser.add_argument("--start_sign", default="<start>", type=str, required=False, help="序列开始标记")
    parser.add_argument("--end_sign", default="<end>", type=str, required=False, help="序列结束标记")
    parser.add_argument("--unk_sign", default="<unk>", type=str, required=False, help="未登录词")
    parser.add_argument("--encoder_save_path", default="models\\tensorflow\\seq2seq\\encoder", type=str,
                        required=False, help="Encoder的SaveModel格式保存路径")
    parser.add_argument("--decoder_save_path", default="models\\tensorflow\\seq2seq\\decoder", type=str,
                        required=False, help="Decoder的SaveModel格式保存路径")

    options = parser.parse_args().__dict__
    execute_type = options["act"]
    if options["config_file"] != "":
        with open(options["config_file"], "r", encoding="utf-8") as config_file:
            options = json.load(config_file)

    # 注意了有关路径的参数，以tensorflow目录下为基准配置
    file_path = os.path.abspath(__file__)
    work_path = file_path[:file_path.find("tensorflow")]

    encoder = seq2seq.encoder(
        vocab_size=options["vocab_size"], embedding_dim=options["embedding_dim"], num_layers=options["encoder_layers"],
        enc_units=options["units"] // 2, cell_type=options["cell_type"], if_bidirectional=options["if_bidirectional"]
    )
    decoder = seq2seq.decoder(
        vocab_size=options["vocab_size"], embedding_dim=options["embedding_dim"], dec_units=options["units"],
        enc_units=options["units"], num_layers=options["decoder_layers"], cell_type=options["cell_type"]
    )

    loss_metric = tf.keras.metrics.Mean(name="loss_metric")
    accuracy_metric = tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy_metric")
    optimizer = tf.optimizers.Adam(name="optimizer")
    checkpoint_manager = load_checkpoint(
        checkpoint_dir=work_path + options["checkpoint_dir"], execute_type=execute_type,
        encoder=encoder, decoder=decoder, checkpoint_save_size=options["checkpoint_save_size"]
    )

    modules = Seq2SeqModule(
        loss_metric=loss_metric, accuracy_metric=accuracy_metric, batch_size=options["batch_size"],
        buffer_size=options["buffer_size"], max_sentence=options["max_sentence"], train_data_type="read_single_data",
        valid_data_type="read_single_data", dict_path=work_path + options["dict_path"], encoder=encoder, decoder=decoder
    )

    if execute_type == "pre_treat":
        preprocess_dataset(dataset_name="lccc", raw_data_path=work_path + options["resource_data_path"],
                           tokenized_data_path=work_path + options["tokenized_data_path"], remove_tokenized=True)
        to_single_turn_dataset(tokenized_data_path=work_path + options["tokenized_data_path"],
                               dict_path=work_path + options["dict_path"], unk_sign=options["unk_sign"],
                               start_sign=options["start_sign"], end_sign=options["end_sign"],
                               max_data_size=options["max_train_data_size"], vocab_size=options["vocab_size"],
                               qa_data_path=work_path + options["preprocess_data_path"])
    elif execute_type == "train":
        history = {"train_accuracy": [], "train_loss": [], "valid_accuracy": [], "valid_loss": []}
        tokenizer = load_tokenizer(dict_path=work_path + options["dict_path"])
        history = modules.train(
            optimizer=optimizer, epochs=options["epochs"], checkpoint=checkpoint_manager, history=history,
            train_data_path=work_path + options["preprocess_data_path"], valid_data_path="",
            checkpoint_save_freq=options["checkpoint_save_freq"], max_valid_data_size=options["max_valid_data_size"],
            max_train_data_size=options["max_train_data_size"], valid_data_split=options["valid_data_split"],
            start_sign=tokenizer.word_index.get(options["start_sign"]),
            encoder_save_path=work_path + options["encoder_save_path"],
            decoder_save_path=work_path + options["decoder_save_path"]
        )
        show_history(history=history, valid_freq=options["checkpoint_save_freq"],
                     save_dir=work_path + options["history_image_dir"])
    elif execute_type == "evaluate":
        tokenizer = load_tokenizer(dict_path=work_path + options["dict_path"])
        modules.evaluate(
            max_valid_data_size=options["max_valid_data_size"], valid_data_path=work_path + options["valid_data_path"],
            start_sign=tokenizer.word_index.get(options["start_sign"])
        )
    elif execute_type == "chat":
        print("Agent: 你好！结束聊天请输入ESC。")
        while True:
            request = input("User: ")
            if request == "ESC":
                print("Agent: 再见！")
                exit(0)
            response = modules.inference(request=request, beam_size=options["beam_size"],
                                         start_sign=options["start_sign"], end_sign=options["end_sign"])
            print("Agent: ", response)
    else:
        parser.error(message="")


if __name__ == "__main__":
    tf_seq2seq()
