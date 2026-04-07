<template>
  <div class="chat-container">
    <div class="messages" ref="messagesContainer">
      <!-- 遍历显示历史消息 -->
      <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
        <!-- 助手头像图标 -->
        <img v-if="msg.role === 'assistant'" src="/favicon.jpeg" alt="avatar" width="28" height="28" class="avatar" />
        <div v-if="msg.role !== 'system'" class="content" v-html="renderMarkdown(msg.content)"></div>
      </div>

      <!-- 流式输出中的占位消息 -->
      <div v-if="isStreaming" class="message assistant">
        <img src="../public/favicon.jpeg" alt="avatar" width="28" height="28" class="avatar" />
        <div class="content">
          <span v-html="renderMarkdown(streamingContent)"></span>

          <span class="typing-cursor"></span>
        </div>
      </div>
    </div>
    <!-- 底部输入区 -->
    <div class="input-area-wrapper">
      <div class="input-area">
        <el-input v-model="inputText" class="input-content" @keyup.enter="sendMessage" :disabled="isStreaming" placeholder="输入消息..." />
        <el-button round type="primary" size="large" @click="sendMessage" :disabled="isStreaming || isUploading">
          {{ isStreaming ? 'AI 正在回复...' : isUploading ? '上传中...' : '发送' }}
        </el-button>
      </div>
      <UploadFile @upload-status="handleUploadStatus" />
    </div>
  </div>
</template>

<script setup>
import './assets/styles/new.css'
import { ref, nextTick } from 'vue'

import { marked } from 'marked'
import hljs from 'highlight.js'
import UploadFile from './components/UploadFile.vue'

// 配置 marked
marked.setOptions({
  highlight: function (code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

const renderMarkdown = (content) => {
  if (!content) return ''
  return marked.parse(content, { async: false })
}

const messages = ref([
  { role: 'assistant', content: '你好！我是 **AI 醋醋**，可以帮你解决任何问题。' },
  {
    role: 'system',
    content: '你是一位专业的AI助手，回答要用柯基犬可爱的风格，使用中文。'
  }
])

const inputText = ref('')
const isStreaming = ref(false)
const isUploading = ref(false)
const streamingContent = ref('')
const messagesContainer = ref(null)

const handleUploadStatus = (data) => {
  isUploading.value = data.status === 0
}
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  if (!inputText.value.trim() || isStreaming.value) return

  const userMessage = inputText.value.trim()
  messages.value.push({ role: 'user', content: userMessage })
  inputText.value = ''
  await scrollToBottom()

  isStreaming.value = true
  streamingContent.value = ''

  let assistantContent = ''

  try {
    const response = await fetch('/v1/upload-file-chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: messages.value.map(msg => ({ role: msg.role, content: msg.content }))
      })
    })

    const reader = response.body.getReader() // 原生的fetch请求支持流式读取响应体
    const decoder = new TextDecoder() // 用于解码二进制数据
    let buffer = ''

    while (true) {
      //循环取块
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true }) // 追加到缓冲区
      const lines = buffer.split('\n') // 按行分割
      buffer = lines.pop() || ''// 最后一行可能不完整，留到下次

      for (const line of lines) {
        if (line.startsWith('data: ')) { // SSE 格式要求
          const data = line.slice(6) // 去掉 "data: " 前缀
          if (data === '{"done": true}') {
            messages.value.push({
              role: 'assistant',
              content: assistantContent
            })
            streamingContent.value = ''
            await scrollToBottom()
            break
          }

          try {
            const parsed = JSON.parse(data)
            if (parsed.error) {
              console.error('后端错误:', parsed.error)
              streamingContent.value = `错误：${parsed.error}`
              // 添加错误标记，避免继续累积
              assistantContent = ''
              break
            }
            if (parsed.content) {
              assistantContent += parsed.content// 累积完整回答
              streamingContent.value = assistantContent // 实时显示
              await scrollToBottom()
            }
            if (parsed.error) {
              console.error('后端错误:', parsed.error)
              streamingContent.value = '错误：' + parsed.error
              await scrollToBottom()
            }
          } catch (e) {
            console.error('解析错误:', e)
          }
        }
      }
    }
  } catch (error) {
    console.error('请求失败:', error)
    streamingContent.value = '网络错误，请稍后重试'
    await scrollToBottom()
  } finally {
    isStreaming.value = false
  }
}
</script>
