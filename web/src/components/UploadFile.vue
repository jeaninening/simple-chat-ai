<template>
  <div class="uploade-icon" >
    <div>
      <el-upload
        :show-file-list="true"
        :http-request="customUpload"
        accept=".pdf,.docx,.txt"
        :on-remove="deleteFile"
        :limit="1"
      >
        <UploadFilled style="width: 18px; height: 18px;margin-right: 8px;" />
        <span style="color: #666; font-size: 12px;">上传后可直接对文档内容提问,支持PDF / Word / TXT</span>
      </el-upload>
    </div>
    </div>  
</template>

<script setup>
import { ref } from 'vue'
import UploadFilled from "../assets/icons/upload.svg"
import request from '@/utils/request'
const emit = defineEmits(['upload-status'])
const file_id = ref(null)

// 自定义上传（必触发 progress）
const customUpload = async (options) => {
  const { file } = options

  const formData = new FormData()
  formData.append('file', file)

  try {
    // 上传中
    emit('upload-status', { status: 0, message: '文档上传中...' })

    const res = await request({
      url: '/v1/upload',
      method: 'POST',
      data: formData,
      onUploadProgress: (progressEvent) => {
        const percent = Math.floor(
          (progressEvent.loaded / progressEvent.total) * 100
        )
        console.log('上传进度：', percent + '%')
        
        // 向父组件发送进度
        emit('upload-status', {
          status: 0,
          message: `文档上传中... ${percent}%`,
          percent: percent
        })
      }
    })

    // 成功
    if (res.data.code === 200) {
      file_id.value = res.data.file_id
      emit('upload-status', { status: 1 })
    }else{
      throw new Error(res.data.msg);
    }
  } catch (err) {
    console.error(err)
    emit('upload-status', { status: 2 })
  }
}
// 删除文件
const deleteFile = async () => {
  await request("/v1/delete-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    data: { file_id: file_id.value }
  })
  file_id.value = null
}
</script>

<style scoped>
.uploade-icon{
  padding:0 20px 20px;
}

</style>