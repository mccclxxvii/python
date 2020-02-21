import telebot
import time
import re
import pymysql
import pymysql.cursors
from telebot import types
from difflib import SequenceMatcher

def getUser(con,cur,bot,message):
	userID = -1
	cur.execute("SELECT ID,FIRST_NAME FROM T_USER WHERE TELEGRAM_ID='"+str(message.from_user.id)+"'")
	user = cur.fetchall()
	if len(user)==0:
		cur.execute("INSERT INTO T_USER(TELEGRAM_ID,FIRST_NAME,LAST_NAME,NICK_NAME) values('"+str(message.from_user.id)+"','"+str(message.from_user.first_name).replace('\'','\'\'')+"','"+str(message.from_user.last_name).replace('\'','\'\'')+"','"+str(message.from_user.username).replace('\'','\'\'')+"')")
		con.commit()
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
		cur.execute("SELECT ID,FIRST_NAME FROM T_USER WHERE TELEGRAM_ID='"+str(message.from_user.id)+"'")
		user = cur.fetchall()
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
	else:
		cur.execute("UPDATE T_USER SET FIRST_NAME='"+str(message.from_user.first_name).replace('\'','\'\'')+"',LAST_NAME='"+str(message.from_user.last_name).replace('\'','\'\'')+"',NICK_NAME='"+str(message.from_user.username).replace('\'','\'\'')+"' where ID="+str(user[0]["ID"]))
	cur.execute("SELECT * FROM T_USER_BOT ub,T_BOT b WHERE ub.USER_ID="+str(user[0]["ID"])+" AND ub.BOT_ID=b.ID AND b.NAME='@QuizXIVbot'")
	user_bot = cur.fetchall()
	if len(user_bot)==0:
		cur.execute("INSERT INTO T_USER_BOT (USER_ID,BOT_ID) SELECT "+str(user[0]["ID"])+",ID FROM T_BOT WHERE NAME='@QuizXIVbot'")
	con.commit()
	cur.execute("SELECT * FROM T_USER_BOT ub,T_BOT b WHERE ub.USER_ID="+str(user[0]["ID"])+" AND ub.BOT_ID=b.ID AND b.NAME='@QuizXIVbot'")
	user = cur.fetchall()
	con.commit()
	if user[0]['STATUS_CD']=="LOCKED":
		bot.send_message(message.from_user.id,'Извините, ваша учетная запись заблокирована')
	else:
		userID = user[0]['ID']
	return(userID)
	
def getGame(con,cur,userID,bot,tgUserId):
	cur.execute("SELECT q.*,d.QUESTION FROM T_QUEST_MAIN q LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID WHERE q.USER_BOT_ID="+str(userID)+" AND q.STATUS_CD='Active'")
	game = cur.fetchall()
	if len(game)==0:
		cur.execute("INSERT INTO T_QUEST_MAIN(USER_BOT_ID) values("+str(userID)+")")
		con.commit()
		cur.execute("SELECT q.*,d.QUESTION FROM T_QUEST_MAIN q LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID WHERE q.USER_BOT_ID="+str(userID)+" AND q.STATUS_CD='Active'")
		bot.send_message(tgUserId,'Начнем')
		game = cur.fetchall()
	return(game[0])
	
def getNextQuest(con,cur,game):
	res = {}
	mes = []
	but = ["/next","/add"]
	cur.execute("UPDATE T_QUEST_MAIN SET THIS_QUEST_ID=null, MODE_CD='Default',LAST_ANSWER_ID=NULL WHERE ID="+str(game['ID']))
	con.commit()
	cur.execute("SELECT q.* FROM ( SELECT c.*,ROW_NUMBER() over() rwn FROM T_QUEST_DICT c WHERE NOT EXISTS( SELECT 1 FROM T_QUEST_BEEN u WHERE u.GAME_ID="+str(game['ID'])+" AND QUEST_ID=c.ID AND RESULT IS NOT NULL) order by rand()) q where q.rwn=1")
	quest = cur.fetchall()
	if len(quest)>0:
		cur.execute("UPDATE T_QUEST_MAIN SET THIS_QUEST_ID ='"+str(quest[0]['ID'])+"', MODE_CD='Exists Question' WHERE ID="+str(game['ID']))
		con.commit()
		mes.append(str(quest[0]['QUESTION']))
		but.append("/get")
	else:
		mes.append('Вопросы закончились')
	res['messages']=mes
	res['buttons']=but
	return (res)

def userMoveCheck(con,cur,game,answer):
	res = {}
	mes = []
	but = ["/next","/add","/get","/dispute","/why"]
	cur.execute("select d.ANSWER from T_QUEST_DICT d WHERE d.ID="+str(game['THIS_QUEST_ID'])+" union ALL select v.VAL ANSWER from T_QUEST_DICT_VAR v WHERE v.QUEST_ID="+str(game['THIS_QUEST_ID']))
	quest = cur.fetchall()
	for ans in quest:
		x = re.sub("[^A-ZА-ЯЇІЄ0-9]","",str(ans['ANSWER']).upper())
		y = re.sub("[^A-ZА-ЯЇІЄ0-9]","",answer.upper())
		if SequenceMatcher(None, x, y).ratio()>0.85:
			s=1
		elif x.find(y)>=0 and len(y)>5:
			s=1
		elif y.find(x)>=0 and len(x)>5:
			s=1
		else:
			s=0
		if s==1:
			rightAnswer = ans['ANSWER']
			break
	cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID FROM T_QUEST_BEEN")
	rowId = cur.fetchall()[0]['ROW_ID']
	if s==0:
		mes.append("Ответ '"+answer+"' не принят.")
		cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER) VALUES("+str(rowId)+","+str(game['ID'])+","+str(game['THIS_QUEST_ID'])+",'"+str(answer)+"')")
	else:
		mes.append("Ответ '"+rightAnswer+"' принят.")
		cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER,RESULT) VALUES("+str(rowId)+","+str(game['ID'])+","+str(game['THIS_QUEST_ID'])+",'"+str(answer)+"','Correct')")
	cur.execute("UPDATE T_QUEST_MAIN SET LAST_ANSWER_ID='"+str(rowId)+"', MODE_CD='Exists Answer' WHERE ID="+str(game['ID']))
	con.commit()
	res['messages']=mes
	res['buttons']=but
	return (res)

def editMode(con,cur,game,mode):
	res = {}
	mes = []
	but = ["/cancel"]
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD='"+mode+"' WHERE ID="+str(game['ID']))
	con.commit()
	if mode=="Dispute":
		mes.append('Введите комментарий')
	else:
		mes.append('Введите вопрос')
	res['messages']=mes
	res['buttons']=but
	return (res)

def getAnswer(con,cur,game):
	res = {}
	mes = []
	but = ["/next","/add","/dispute","/why"]
	cur.execute("SELECT d.ANSWER FROM T_QUEST_MAIN m, T_QUEST_DICT d WHERE m.THIS_QUEST_ID=d.ID AND m.ID="+str(game['ID']))
	answer = cur.fetchall()
	mes.append(str(answer[0]["ANSWER"]))
	cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID FROM T_QUEST_BEEN")
	rowId = cur.fetchall()[0]['ROW_ID']
	cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER,RESULT) VALUES("+str(rowId)+","+str(game['ID'])+","+str(game['THIS_QUEST_ID'])+",'"+str(answer[0]["ANSWER"])+"','Pass')")
	cur.execute("UPDATE T_QUEST_MAIN SET LAST_ANSWER_ID='"+str(rowId)+"' WHERE ID="+str(game['ID']))
	con.commit()
	res['messages']=mes
	res['buttons']=but
	return (res)

def getComment(con,cur,game):
	res = {}
	mes = []
	but = ["/next","/add","/dispute"]
	cur.execute("SELECT d.ANSWER,nvl(d.COMMENTS,'Просто так') COMMENTS FROM T_QUEST_MAIN m, T_QUEST_DICT d WHERE m.THIS_QUEST_ID=d.ID AND m.ID="+str(game['ID']))
	answer = cur.fetchall()
	for ans in answer:
		mes.append(str(ans["COMMENTS"]))
	res['messages']=mes
	res['buttons']=but
	return (res)

def cancelOperation(con,cur,game):
	res = {}
	mes = []
	but = ["/next","/add"]
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD='Default' WHERE ID="+str(game['ID']))
	con.commit()
	mes.append("Вы можете выбрать следующий вопрос или добавить новый")
	res['messages']=mes
	res['buttons']=but
	return (res)

def firstStepAddQuest(con,cur,game,text):
	res = {}
	mes = []
	but = ["/cancel"]
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD='Add Answer',TEMP_STR='"+text.replace('\'','\'\'')+"' WHERE ID="+str(game['ID']))
	con.commit()
	mes.append("Введите ответ (варианты строго через запятую и пробел)")
	res['messages']=mes
	res['buttons']=but
	return (res)

def secondStepAddQuest(con,cur,game,text):
	res = {}
	mes = []
	but = ["/next","/add"]
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD ='Default',TEMP_STR=null WHERE ID="+str(game['ID']))
	con.commit()
	answers = text.split(', ')
	cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID FROM T_QUEST_DICT")
	rowId = cur.fetchall()[0]['ROW_ID']
	cur.execute("INSERT INTO T_QUEST_DICT(ID,QUESTION,ANSWER,CREATED_BY) VALUES("+str(rowId)+",'"+str(game['TEMP_STR'])+"','"+str(answers[0])+"',"+str(game['USER_BOT_ID'])+")")
	for i in range(1,len(answers)):
		cur.execute("INSERT INTO T_QUEST_DICT_VAR (QUEST_ID,VAL) VALUES("+str(rowId)+",'"+str(answers[i])+"')")
	con.commit()
	mes.append("Спасибо, [Name]. Вопрос добавлен")
	res['messages']=mes
	res['buttons']=but
	return (res)

def disputeQuest(con,cur,game,text):
	res = {}
	mes = []
	but = ["/next","/add"]
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD='Default' WHERE ID="+str(game['ID']))
	con.commit()
	if not game['LAST_ANSWER_ID']:
		cur.execute("INSERT INTO T_QUEST_BEEN (GAME_ID,QUEST_ID,DISPUTE_FLG,COMMENTS) VALUES ("+str(game['ID'])+","+str(game['THIS_QUEST_ID'])+",1,'"+str(text)+"')")
	else:
		cur.execute("UPDATE T_QUEST_BEEN SET DISPUTE_FLG=1,COMMENTS='"+str(text)+"' WHERE ID="+str(game['LAST_ANSWER_ID']))
	con.commit()
	mes.append("Спасибо, учту")
	res['messages']=mes
	res['buttons']=but
	return (res)

def defaultFunc():
	res = {}
	mes = []
	but = ["/next","/add"]
	mes.append("Вы можете выбрать следующий вопрос или добавить новый")
	res['messages']=mes
	res['buttons']=but
	return (res)

def main(bot,type,message):
	try:
		if 1==1:
		#if message.from_user.id==394246173:  #ЗАГЛУШКА
			con = pymysql.connect(host='176.36.217.49',port=3307,user='TELEGRAM_BOT',password='!1qaZXsw2@',db='NasDB',charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor)
			cur = con.cursor()
			try:
				userID = getUser(con,cur,bot,message)
				if userID>=0:
					game = getGame(con,cur,userID,bot,message.from_user.id)
					func = {
						"Exists Question":{#есть новый вопрос
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"add":"editMode(con,cur,game,'Add Question')",#добавить новый вопрос
							"get":"getAnswer(con,cur,game)",#узнать ответ
							"default":"userMoveCheck(con,cur,game,message.text)",#ввод ответа
							"dispute":"editMode(con,cur,game,'Dispute')",#оспроить вопрос
							"why":"getComment(con,cur,game)"#почему?
						},
						"Exists Answer":{#есть введенный вопрос
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"add":"editMode(con,cur,game,'Add Question')",#добавить новый вопрос
							"get":"getAnswer(con,cur,game)",#узнать ответ
							"dispute":"editMode(con,cur,game,'Dispute')",#оспроить вопрос
							"default":"userMoveCheck(con,cur,game,message.text)",#ввод ответа
							"why":"getComment(con,cur,game)"#почему?
						},
						"Add Question":{#режим добавления вопроса
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"cancel":"cancelOperation(con,cur,game)",#отменить
							"default":"firstStepAddQuest(con,cur,game,message.text)"#ввод нового вопроса
						},
						"Add Answer":{#режим добавления ответа
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"cancel":"cancelOperation(con,cur,game)",#отменить
							"default":"secondStepAddQuest(con,cur,game,message.text)"#ввод нового ответа
						},
						"Dispute":{#режим оспаривания
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"cancel":"cancelOperation(con,cur,game)",#отменить
							"default":"disputeQuest(con,cur,game,message.text)",#ввод комментария
						},
						"Default":{
							"next":"getNextQuest(con,cur,game)",#перейти к следующему вопросу
							"add":"editMode(con,cur,game,'Add Question')",#добавить новый вопрос
							"default":"defaultFunc()"#игнорировать
						},
					}
					x = ""
					try:
						x = func[game['MODE_CD']][type]
					except Exception as f:
						print(game['MODE_CD'],type)
					if len(x)==0:
						result = defaultFunc()
					else:
						result = eval(func[game['MODE_CD']][type])
					markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
					for button in result['buttons']:
						itembtn = types.KeyboardButton(button)
						markup.add(itembtn)
					for mess in result['messages']:
						bot.send_message(message.from_user.id, mess.replace('[Name]',str(message.from_user.first_name)), reply_markup=markup)
			except Exception as e:
				bot.send_message(message.from_user.id,"Ошибка:"+str(e))
			cur.close()
			con.close()
	except Exception as e:
		bot.send_message(message.from_user.id,"Ошибка:"+str(e))

try:
	bot = telebot.TeleBot("959911904:AAHlPuS8mMdsqQrMmdIG0h5Y9COtyFbCpfs")
	@bot.message_handler(commands=['next'])
	def command_next(message):
		main(bot,'next',message)
	@bot.message_handler(commands=['add'])
	def command_add(message):
		main(bot,'add',message)
	@bot.message_handler(commands=['dispute'])
	def command_disp(message):
		main(bot,'dispute',message)
	@bot.message_handler(commands=['why'])
	def command_next(message):
		main(bot,'why',message)
	@bot.message_handler(commands=['cancel'])
	def command_next(message):
		main(bot,'cancel',message)
	@bot.message_handler(commands=['get'])
	def command_next(message):
		main(bot,'get',message)
	@bot.message_handler(content_types=['text'])
	def get_text_messages(message):
		main(bot,'default',message)
	bot.polling(none_stop=False, interval=1)
except Exception as e:
	print(e)
