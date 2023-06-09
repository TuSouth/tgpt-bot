from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

from pathlib import Path
import tempfile
import pydub

import openai_utils

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


async def voice_to_speech(voice_file_id: str, context) -> str:
    # 临时文件存储录音文件
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        voice_ogg_path = tmp_dir / "group_voice.ogg"

        # download 下载语音文件
        voice_file = await context.bot.get_file(voice_file_id)
        await voice_file.download_to_drive(voice_ogg_path)

        # convert to mp3
        voice_mp3_path = tmp_dir / "gourp_voice.mp3"
        pydub.AudioSegment.from_file(voice_ogg_path).export(voice_mp3_path, format="mp3")

        # transcribe
        with open(voice_mp3_path, "rb") as f:
            transcribed_text = await openai_utils.transcribe_audio(f)

            if transcribed_text is None:
                 transcribed_text = "" 

        return transcribed_text

# 处理语音信息
async def voice_message_handle(update: Update, context: CallbackContext):

    try:
        chat_id = update.effective_chat.id
        bot = context.bot

        # send placeholder message to user
        placeholder_message = await bot.send_message(chat_id=chat_id, text="...")

        # send typing action
        await bot.send_chat_action(chat_id=chat_id, action="typing")

        voice = update.message.voice

        transcribed_text = await voice_to_speech(voice.file_id, context)

        if len(transcribed_text) <= 15:
            text = f"🎤: <i>{transcribed_text}</i>"
        else:
            # 如果消息长度大于15，则使用ChatGPT获取一个50个字以内的总结
            # await message_handle(update, context, message=transcribed_text)
            short_summary = await openai_utils.get_short_summary(transcribed_text)
            text = f"🎤 摘要: <i>{short_summary}</i>"
        
        # await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        parse_mode = ParseMode.HTML
        await context.bot.edit_message_text(text, chat_id=placeholder_message.chat_id, message_id=placeholder_message.message_id, parse_mode=parse_mode)


    except Exception as e:
        error_text = f"Something went wrong during completion. Reason: {e}"
        logger.error(error_text)
        await bot.send_message(chat_id=chat_id, text=error_text)

# 处理回复消息
async def handle_voice_reply(update: Update, context: CallbackContext):
    message = update.message
    voice = None
    if message.reply_to_message and message.reply_to_message.voice:
        voice = message.reply_to_message.voice
    elif message.voice:
        voice = message.voice
    else:
        raise ValueError("No voice message found.")

    await voice_summary_handle(update, context, voice)

# 语音信息总结
async def voice_summary_handle(update: Update, context: CallbackContext, voice):

    try:
        bot = context.bot
        chat_id = update.effective_chat.id

        placeholder_message = await bot.send_message(chat_id=chat_id, text="...")
        # send typing action
        await bot.send_chat_action(chat_id=chat_id, action="typing")
   
        transcribed_text = await voice_to_speech(voice.file_id, context)
        text = f"🎤: <i>{transcribed_text}</i>"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        summary = await openai_utils.get_summary(text)
        await update.message.reply_text(summary, parse_mode=ParseMode.HTML)
    
    except Exception as e:
        error_text = f"Something went wrong during completion. Reason: {e}"
        logger.error(error_text)
        await context.bot.send_message(chat_id=chat_id, text=error_text)