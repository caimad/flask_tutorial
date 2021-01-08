# encoding = utf-8
import hashlib
import base64
import hmac
import json
import wave
from urllib.parse import urlencode
import logging

from wsgiref.handlers import format_date_time
import datetime
from datetime import datetime
import time
from time import mktime
import _thread as thread
import pyaudio
from playsound import playsound
from pypinyin import lazy_pinyin

from ws4py.client.threadedclient import WebSocketClient

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def record_audio(wave_out_path, record_second):
    """ 录音功能 """
    p = pyaudio.PyAudio()  # 实例化对象
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)  # 打开流，传入响应参数
    wf = wave.open(wave_out_path, 'wb')  # 打开 wav 文件。
    wf.setnchannels(CHANNELS)  # 声道设置
    wf.setsampwidth(p.get_sample_size(FORMAT))  # 采样位数设置
    wf.setframerate(RATE)  # 采样频率设置


    for _ in range(0, int(RATE * record_second / CHUNK)):
        data = stream.read(CHUNK)
        wf.writeframes(data)
    stream.stop_stream()  # 关闭流
    stream.close()
    p.terminate()
    wf.close()


class WsParam(object):
    # 初始化
    def __init__(self, AudioFile, APPId="5f1975bd", APIKey="92f2011bc34bc76734dfbccf9f50682b",
                 APISecret="939f279e10ceef3896ab1fcf063a89d6"):
        self.APPId = APPId
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile

        # 公共参数(common)
        self.CommonArgs = {
            'app_id': self.APPId
        }
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {
            'domain': 'iat',
            'language': 'zh_cn',
            'accent': 'cn_lmz',
            'vinfo': 1,
            'vad_eos': 10000,
        }

    # 生成url
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = 'host: ' + 'ws-api.xfyun.cn' + '\n'
        signature_origin += 'date: ' + date + '\n'
        signature_origin += 'GET ' + '/v2/iat ' + 'HTTP/1.1'
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = 'api_key="%s", algorithm="%s", headers="%s", signature="%s"' % (
            self.APIKey, 'hmac-sha256', 'host date request-line', signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            'authorization': authorization,
            'date': date,
            'host': 'ws-api.xfyun.cn'
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        # print('date: ',date)
        # print('v: ',v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        # print('websocket url :', url)
        return url


class Recognition(WebSocketClient):
    def __init__(self, url, ws_param):
        super().__init__(url)
        self.ws_param = ws_param
        self.result_text = ''
        self.result_text_temp = ''

    # 收到websocket消息的处理
    def received_message(self, message):
        message = message.__str__()
        try:
            code = json.loads(message)["code"]
            sid = json.loads(message)["sid"]
            if code != 0:
                errMsg = json.loads(message)["message"]
                print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))

            else:
                data = json.loads(message)["data"]["result"]["ws"]
                # print(json.loads(message))
                result = ""
                for i in data:
                    for w in i["cw"]:
                        result += w["w"]
                self.result_text += result

                print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))

        except Exception as e:
            print("receive msg,but parse exception:", e)

    # 收到websocket错误的处理
    def on_error(self, error):
        logging.error(error)

    # 收到websocket关闭的处理
    def closed(self, code, reason=None):
        logging.info('语音识别通道关闭' + str(code) + str(reason))

    # 收到websocket连接建立的处理
    def opened(self):
        def run(*args):
            # framesize = 8000
            frameSize = 1280  # 每一帧的音频大小
            intervel = 0.04  # 发送音频间隔(单位:s)
            status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

            with open(self.ws_param.AudioFile, "rb") as fp:
                while True:
                    buf = fp.read(frameSize)
                    # 文件结束
                    if not buf:
                        status = STATUS_LAST_FRAME
                    # 第一帧处理
                    # 发送第一帧音频，带business 参数
                    # appid 必须带上，只需第一帧发送
                    if status == STATUS_FIRST_FRAME:

                        d = {"common": self.ws_param.CommonArgs,
                             "business": self.ws_param.BusinessArgs,
                             "data": {"status": 0, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        d = json.dumps(d)
                        self.send(d)
                        status = STATUS_CONTINUE_FRAME
                    # 中间帧处理
                    elif status == STATUS_CONTINUE_FRAME:
                        d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        self.send(json.dumps(d))
                    # 最后一帧处理
                    elif status == STATUS_LAST_FRAME:
                        d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                      "audio": str(base64.b64encode(buf), 'utf-8'),
                                      "encoding": "raw"}}
                        self.send(json.dumps(d))
                        time.sleep(1)
                        break
                    # 模拟音频采样间隔
                    time.sleep(intervel)
            self.close()

        thread.start_new_thread(run, ())


def audio_to_text(AudioFile):
    ws_param = WsParam(AudioFile)

    ws_url = ws_param.create_url()
    ws = Recognition(ws_url, ws_param)
    ws.connect()
    ws.run_forever()
    res = ws.result_text
    return res

class PinyinSimilarity:

    def __init__(self, answer):
        self.answer_hanzi = answer
        self.answer_pinyin = lazy_pinyin(answer)

    def pinyin_similarity(self, str_input):
        str_input = self._change_word_signal(str_input)
        str_input_hanzi = str_input

        # 如果答案直接在识别文本中，直接返回true
        if self.answer_hanzi in str_input_hanzi:
            return True
        # 拼音进行模糊匹配
        str_input_pinyin = lazy_pinyin(str_input)
        str_input_hanzi = []
        for i, char_input_pinyin in enumerate(str_input_pinyin):
            char_input_hanzi = self._match_word(char_input_pinyin)
            if char_input_hanzi:
                str_input_hanzi.append(char_input_hanzi)
            else:
                str_input_hanzi.append([str_input[i]])
        print(str_input_hanzi)
        str_all_hanzi = self.all_output_hanzi(str_input_hanzi)
        for str_hanzi in str_all_hanzi:
            if self.answer_hanzi in str_hanzi:
                return True
            else:
                return False

    def _change_word_signal(self, str_input):
        str_output = str_input
        str_output = str_output.replace("，", "")
        str_output = str_output.replace("。", "")
        str_output = str_output.replace(" ", "")
        str_output = str_output.replace("？", "")
        return str_output

    def _match_word(self, char_pinyin):
        # 拼音精准匹配
        if char_pinyin in self.answer_pinyin:
            return [self.answer_hanzi[i] for i, x in enumerate(self.answer_pinyin) if x == char_pinyin]
        char_pinyin_head = self._match_head(char_pinyin)  # 替换声母
        if char_pinyin_head in self.answer_pinyin:
            return [self.answer_hanzi[i] for i, x in self.answer_pinyin if x == char_pinyin_head]
        char_pinyin_tail = self._match_tail(char_pinyin)  # 替换韵母
        if char_pinyin_tail in self.answer_pinyin:
            return [self.answer_hanzi[i] for i, x in self.answer_pinyin if x == char_pinyin_tail]
        char_pinyin_head_tail = self._match_tail(char_pinyin_head)  # 都替换
        if char_pinyin_head_tail in self.answer_pinyin:
            return [self.answer_hanzi[i] for i, x in self.answer_pinyin if x == char_pinyin_head_tail]
        # 未替换成功
        return None

    def _match_head(self, char_pinyin):
        if char_pinyin in 'zh':
            replaced_char_pinyin = char_pinyin.replace('zh', 'z')
        elif char_pinyin in 'ch':
            replaced_char_pinyin = char_pinyin.replace('ch', 'c')
        elif char_pinyin in 'sh':
            replaced_char_pinyin = char_pinyin.replace('sh', 's')
        elif char_pinyin in 'z':
            replaced_char_pinyin = char_pinyin.replace('z', 'zh')
        elif char_pinyin in 'c':
            replaced_char_pinyin = char_pinyin.replace('c', 'ch')
        elif char_pinyin in 's':
            replaced_char_pinyin = char_pinyin.replace('s', 'ch')
        elif char_pinyin in 'l':
            replaced_char_pinyin = char_pinyin.replace('l', 'n')
        elif char_pinyin.index('n') == 0:
            replaced_char_pinyin = char_pinyin.replace('n', 'l')
        else:
            return char_pinyin
        return replaced_char_pinyin

    def _match_tail(self, char_pinyin):
        if char_pinyin in 'ang':
            replaced_char_pinyin = char_pinyin.replace('ang', 'an')
        elif char_pinyin in 'eng':
            replaced_char_pinyin = char_pinyin.replace('eng', 'en')
        elif char_pinyin in 'ing':
            replaced_char_pinyin = char_pinyin.replace('ing', 'in')
        elif char_pinyin in 'an':
            replaced_char_pinyin = char_pinyin.replace('an', 'ang')
        elif char_pinyin in 'en':
            replaced_char_pinyin = char_pinyin.replace('en', 'eng')
        elif char_pinyin in 'in':
            replaced_char_pinyin = char_pinyin.replace('in', 'ing')
        else:
            return char_pinyin
        return replaced_char_pinyin

    def all_output_hanzi(self, input_str):
        if not input_str:
            return list()

        def backtrack(index: int):
            if index == len(input_str):
                combinations.append("".join(combination))
            else:
                for str2 in input_str[index]:
                    combination.append(str2)
                    backtrack(index + 1)
                    combination.pop()

        combinations = list()
        combination = list()
        backtrack(0)
        return combinations

if __name__ == "__main__":
    # AudioFile参数为空时表示不在本地生成音频文件，是否设置为空可以根据开发需求确定

    # ws_param = WsParam(AudioFile=r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test6.pcm')
    # ws_param = WsParam(AudioFile=r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test7.pcm')
    # ws_param = WsParam(AudioFile=r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test8.pcm')
    # ws_param = WsParam(AudioFile=r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test9.pcm')
    # ws_param = WsParam(AudioFile=r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test10.pcm')
    # file_path = r'C:\Users\ytantao\Desktop\AI测试\刘老师重庆话测试音频\test10.pcm'
    file_path = r'C:\Users\ytantao\Desktop\AI测试\重庆话测试\余-msr-2020-12-15T09-48-46-594ZlateMemory.wav'
    # file_path='output.wav'
    # record_audio(file_path, 5)
    ws_param = WsParam(AudioFile=file_path)
    # playsound(file_path)
    ws_url = ws_param.create_url()
    ws = Recognition(ws_url, ws_param)
    ws.connect()
    ws.run_forever()
    res = ws.result_text
    print(res)

