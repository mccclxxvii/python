import telebot
import pymysql
import pymysql.cursors
from telebot import types
from difflib import SequenceMatcher
from random import shuffle
import sys
from defs import *
#from actions import *

def main(bot,type,input_message,config):
	try:
		con = pymysql.connect(host='176.36.217.49',port=3307,user='TELEGRAM_BOT',password='!1qaZXsw2@',db='NasDB',charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,connect_timeout=30,max_allowed_packet=1000000000)
		global cur,game,result,message,messageFile,file_size
		message = input_message
		cur = con.cursor()
		try:
			user = getUser(cur,bot,message)
			if len(user)>0:
				game = getGame(cur,user['ID'],bot,message.from_user.id)
				if type=="reconfig" and user['ADMIN_FLAG']==1:
					result = reconfigure(cur)
				else:
					if type == 'audio' or type == 'photo':
						messageFile,file_size = getFile(message,type,bot)
					else:
						messageFile,file_size = ("","")
						cur.execute("SELECT DISTINCT BUTTON_NAME,COMMAND FROM "+config)
						cmnds = cur.fetchall()
						for cmnd in cmnds:
							if message.text==cmnd['BUTTON_NAME']:
								type=cmnd['COMMAND']
					cur.execute("SELECT ACTION_SCRIPT FROM "+config+" WHERE STATE=%s and MODE=%s and COMMAND=%s",(game['STATUS_CD'],game['MODE_CD'],type))
					x = cur.fetchall()
					if len(x)==0:
						result = defaultFunc(cur,game)
					else:
						exec(x[0]['ACTION_SCRIPT'],globals())
				markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
				for resbut in result['but']:
					markup.keyboard.append(resbut)
				markup = setMarkup(cur,markup,game,config,type)
				if result['add']['type']=='Картинка':
					bot.send_photo(message.from_user.id,result['add']['val'])
				if result['add']['type']=='Музыкальный':
					bot.send_audio(message.from_user.id,result['add']['val'])
				for mess in result['messages']:
					bot.send_message(message.from_user.id, mess.replace('[Name]',str(message.from_user.first_name)), reply_markup=markup)
			con.commit()
		except Exception as e:
			bot.send_message(message.from_user.id,"Ошибка:"+str(e))
			con.rollback()
		cur.close()
		con.close()
	except Exception as e:
		bot.send_message(message.from_user.id,"Ошибка:"+str(e))

def start(mode):
	try:
		if mode == 'debug':
			bot = telebot.TeleBot("966106908:AAExfZn2rbdcJxyIUDmDUWF31JO7VWkj7NE")
			config = 'V_QUEST_CONFIG'
		else:
			bot = telebot.TeleBot("959911904:AAHlPuS8mMdsqQrMmdIG0h5Y9COtyFbCpfs")
			config = 'T_QUEST_CONFIG'
		@bot.message_handler(content_types=['audio'])
		def handle_docs_file(message):
			main(bot,'audio',message,config)
		@bot.message_handler(content_types=['photo'])
		def handle_docs_file(message):
			main(bot,'photo',message,config)
		@bot.message_handler(content_types=['text'])
		def get_text_messages(message):
			if message.text=="Reconfigure":
				main(bot,'reconfig',message,config)
			else:
				main(bot,'default',message,config)
		bot.polling(none_stop=False, interval=1)
	except Exception as e:
		start(mode)

if __name__=="__main__":
	mode = 'default'
	if len(sys.argv)>1:
		if sys.argv[1]=='debug': mode = 'debug'
	start(mode)