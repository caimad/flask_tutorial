/**
 * Created by lycheng on 2019/8/1.
 *
 * 语音听写流式 WebAPI 接口调用示例 接口文档（必看）：https://doc.xfyun.cn/rest_api/语音听写（流式版）.html
 * webapi 听写服务参考帖子（必看）：http://bbs.xfyun.cn/forum.php?mod=viewthread&tid=38947&extra=
 * 语音听写流式WebAPI 服务，热词使用方式：登陆开放平台https://www.xfyun.cn/后，找到控制台--我的应用---语音听写---个性化热词，上传热词
 * 注意：热词只能在识别的时候会增加热词的识别权重，需要注意的是增加相应词条的识别率，但并不是绝对的，具体效果以您测试为准。
 * 错误码链接：
 * https://www.xfyun.cn/doc/asr/voicedictation/API.html#%E9%94%99%E8%AF%AF%E7%A0%81
 * https://www.xfyun.cn/document/error-code （code返回错误码时必看）
 * 语音听写流式WebAPI 服务，方言或小语种试用方法：登陆开放平台https://www.xfyun.cn/后，在控制台--语音听写（流式）--方言/语种处添加
 * 添加后会显示该方言/语种的参数值
 *
 */

// 1. websocket连接：判断浏览器是否兼容，获取websocket url并连接，这里为了方便本地生成websocket url
// 2. 获取浏览器录音权限：判断浏览器是否兼容，获取浏览器录音权限，
// 3. js获取浏览器录音数据
// 4. 将录音数据处理为文档要求的数据格式：采样率16k或8K、位长16bit、单声道；该操作属于纯数据处理，使用webWork处理
// 5. 根据要求（采用base64编码，每次发送音频间隔40ms，每次发送音频字节数1280B）将处理后的数据通过websocket传给服务器，
// 6. 实时接收websocket返回的数据并进行处理

// ps: 该示例用到了es6中的一些语法，建议在chrome下运行

let recorder;
let status = 'end';
    function invokeGetDisplayMedia(success, error) {
        let displaymediastreamconstraints = {
            audio: true
        };
        if (navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia(displaymediastreamconstraints).then(success).catch(error);
        }
    }
    function captureScreen(callback) {
        this.invokeGetDisplayMedia((mediaStream) => {
            callback(mediaStream);
        }, function (error) {
            console.error(error);
            alert('Unable to capture your screen. Please check console logs.\n' + error);
        });
    }
function startRecording() {
    captureScreen(mediaStream => {
        recorder = RecordRTC(mediaStream, {
            type: 'audio',
            mimeType: 'audio/wav;',
            recorderType: StereoAudioRecorder,
            desiredSampRate: 16000,
            numberOfAudioChannels: 1,
        });
        recorder.startRecording();
        // release screen on stopRecording
        status = 'ing';
        onWillStatusChange('end','ing');
    });
}

function stopRecordingCallback() {
    blob = recorder.getBlob();
    var file = new File([blob], 'msr-' + (new Date).toISOString().replace(/:|\./g, '-')  + '.wav', {
        type: 'audio/wav'
    });
// create FormData
    var formData = new FormData();
    formData.append('audio-filename', file.name);
    formData.append('audio-blob', file);
    console.log(formData);
    $.ajax({
        url:'/ars',
        type:'POST',
        contentType:false,
        data:formData,
        processData:false,
        success: function(result){
            console.log(result)
            $('#result_output').text(result)
        }
    })
    recorder.destroy();
    recorder = null;
    status = 'end';
    onWillStatusChange('ing','end');
}

function onWillStatusChange(oldStatus, status) {
  // 可以在这里进行页面中一些交互逻辑处理：倒计时（听写只有60s）,录音的动画，按钮交互等
  // 按钮中的文字
  let text = {
    null: '开始识别', // 最开始状态
    init: '开始识别', // 初始化状态
    ing: '结束识别', // 正在录音状态
    end: '开始识别', // 结束状态
  }
  let senconds = 0
  $('.taste-button')
    .removeClass(`status-${oldStatus}`)
    .addClass(`status-${status}`)
    .text(text[status])
  if (status === 'ing') {
    $('hr').addClass('hr')
    $('.taste-content').css('display', 'none')
    $('.start-taste').addClass('flex-display-1')
    // 倒计时相关
      $('.time-box').show()
    $('.used-time').text('00：00')
    countInterval = setInterval(()=>{
      senconds++
      $('.used-time').text(`0${Math.floor(senconds/60)}：${Math.floor(senconds/10)}${senconds%10}`)
      if (senconds >= 60) {
        this.stop()
        clearInterval(countInterval)
      }
    }, 1000)
  }  else {
    $('.time-box').hide()
    $('hr').removeClass('hr')
    clearInterval(countInterval)
  }
}

$('#taste_button, .taste-button').click(function() {
  if (status === 'end') {
    startRecording()
  } else {
    recorder.stopRecording(stopRecordingCallback);
  }
})