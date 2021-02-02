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
"""执行Modules之前的预处理模块
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from dialogue.tools import log_operator


def to_single_turn_dataset(tokenized_data_path: str, qa_data_path: str, dict_path: str, vocab_size: int,
                           start_sign: str = "<start>", end_sign: str = "<end>", unk_sign: str = "<unk>",
                           max_data_size: int = 0, remove_tokenized: bool = True):
    """生成单轮对话数据集

    用于处理已经分词好的多轮次数据集的方法，将数据集处理成问答对的形式
    :param tokenized_data_path: 已切分多轮对话数据路径
    :param qa_data_path: 单轮对话数据保存路径
    :param dict_path: 字典保存路径
    :param vocab_size: 词汇量大小
    :param start_sign: 开始标记
    :param end_sign: 结束标记
    :param unk_sign: 未登录词
    :param max_data_size: 最大加载数据量，,0为所有数据
    :param remove_tokenized: 是否移除原有分词文本
    :return: 无返回值
    """
    count = 0
    sentences_count = 0
    max_len = 0
    min_len = 10000
    sentence_len = []
    one_pair = []
    all_text_list = []

    # 对每一轮对话上下文进行配对，形成一问一答两个部分，如果遇到下一轮对话，直接跳过
    with open(tokenized_data_path, encoding="utf-8") as raw_file, \
            open(qa_data_path, "w", encoding="utf-8") as single_turn_data_file:
        for line in raw_file:
            line = line.strip("\n").replace("/", "")
            # line = re.sub(r"[%s]+" % punctuation, "", line)
            # 因为原始数据集中，是一轮一轮的对话排列的，所以需要注意的是
            # 在一轮对话结束之后，最后一句不能作为问句，需要跳到下一轮进行处理
            if line == "":
                one_pair = []
                count += 1
                continue
            elif len(one_pair) == 1:
                one_pair.append(line)
                question = start_sign + " " + one_pair[0] + " " + end_sign
                answer = start_sign + " " + one_pair[1] + " " + end_sign
                single_turn_data_file.write(question + "\t" + answer + "\n")
                all_text_list.append(question)
                all_text_list.append(answer)
                one_pair = [line]
                sentences_count += 1
                print("\r已处理：{}个问答对".format(sentences_count), flush=True, end="")
                if sentences_count == max_data_size:
                    break
            else:
                one_pair.append(line)

            length = len(line)
            max_len = max(max_len, length)
            min_len = min(min_len, length)
            sentence_len.append(length)

    tokenizer = tf.keras.preprocessing.text.Tokenizer(filters="", num_words=vocab_size, oov_token=unk_sign)
    tokenizer.fit_on_texts(all_text_list)
    with open(dict_path, "w", encoding="utf-8") as dict_file:
        dict_file.write(tokenizer.to_json())

    message = "对话数据集转换完毕，并保存字典：共处理{}轮对话数据，整理出{}对" \
              "问答对，语句最大长度：{}，语句最短长度{}，语句平均长度{:.3f}".format(count, sentences_count,
                                                           max_len, min_len, np.mean(sentence_len))
    print("\n" + message)
    logger = log_operator(level=10)
    logger.info(message)