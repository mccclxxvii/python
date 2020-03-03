import telebot
import time
import re
import pymysql
import pymysql.cursors
from telebot import types
from difflib import SequenceMatcher
import sys
from random import shuffle

def getUser(cur,bot,message):
	userID = -1
	cur.execute("SELECT ID,FIRST_NAME "
				+"FROM T_USER "
				+"WHERE TELEGRAM_ID='"+str(message.from_user.id)+"'")
	user = cur.fetchall()
	if len(user)==0:
		cur.execute("INSERT INTO T_USER(TELEGRAM_ID,FIRST_NAME,LAST_NAME,NICK_NAME) values('"
									+str(message.from_user.id)+"','"
									+str(message.from_user.first_name).replace('\'','\'\'')+"','"
									+str(message.from_user.last_name).replace('\'','\'\'')+"','"
									+str(message.from_user.username).replace('\'','\'\'')+"')")
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
		cur.execute("SELECT ID,FIRST_NAME "
					+"FROM T_USER "
					+"WHERE TELEGRAM_ID='"+str(message.from_user.id)+"'")
		user = cur.fetchall()
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
	else:
		cur.execute("UPDATE T_USER "
					+"SET FIRST_NAME='"+str(message.from_user.first_name).replace('\'','\'\'')+"',"
					+"LAST_NAME='"+str(message.from_user.last_name).replace('\'','\'\'')+"',"
					+"NICK_NAME='"+str(message.from_user.username).replace('\'','\'\'')+"' "
					+"where ID="+str(user[0]["ID"]))
	cur.execute("SELECT * FROM T_USER_BOT ub,T_BOT b "
				+"WHERE ub.USER_ID="+str(user[0]["ID"])
				+" AND ub.BOT_ID=b.ID AND b.NAME='@QuizXIVbot'")
	user_bot = cur.fetchall()
	if len(user_bot)==0:
		cur.execute("INSERT INTO T_USER_BOT (USER_ID,BOT_ID) "
					+"SELECT "+str(user[0]["ID"])+",ID "
					+"FROM T_BOT "
					+"WHERE NAME='@QuizXIVbot'")
	cur.execute("SELECT * FROM T_USER_BOT ub,T_BOT b "
				+"WHERE ub.USER_ID="+str(user[0]["ID"])
				+" AND ub.BOT_ID=b.ID"
				+" AND b.NAME='@QuizXIVbot'")
	user = cur.fetchall()
	if user[0]['STATUS_CD']=="LOCKED":
		bot.send_message(message.from_user.id,'Извините, ваша учетная запись заблокирована')
	else:
		userID = user[0]['ID']
	return(userID)
	
def getGame(cur,userID,bot,tgUserId):
	cur.execute("SELECT q.*,d.QUESTION, d.TYPE_CD "
				+"FROM T_QUEST_MAIN q "
				+"LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID "
				+"WHERE q.USER_BOT_ID="+str(userID))
	game = cur.fetchall()
	if len(game)==0:
		cur.execute("INSERT INTO T_QUEST_MAIN(USER_BOT_ID) "
					+"values("+str(userID)+")")
		cur.execute("SELECT q.*,d.QUESTION, d.TYPE_CD "
					+"FROM T_QUEST_MAIN q "
					+"LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID "
					+"WHERE q.USER_BOT_ID="+str(userID))
		bot.send_message(tgUserId,'Начнем')
		game = cur.fetchall()
	return(game[0])

def getNextQuest(cur,game):
	res = {}
	mes = []
	but = []
	add = {"type":"","val":""}
	if game['SEARCH_SPEC']:
		search_spec = game['SEARCH_SPEC']
	else:
		search_spec = '1=1'
	cur.execute("SELECT q.* FROM "
				+"(SELECT c.*,ROW_NUMBER() over() rwn "
					+"FROM V_QUEST_NEXT_DICT c "
					+"WHERE ID=ID AND NOT EXISTS("
								+"SELECT 1 FROM T_QUEST_BEEN u "
								+"WHERE u.GAME_ID="+str(game['ID'])+" AND QUEST_ID=c.ID AND RESULT IS NOT NULL"
					+") AND "+search_spec+" order by rand()) q "
				+"where q.rwn=1")
	quest = cur.fetchall()
	if len(quest)>0:
		cur.execute("UPDATE T_QUEST_MAIN "
					+"SET THIS_QUEST_ID ='"+str(quest[0]['ID'])+"', "
					+"MODE_CD='Default', "
					+"STATUS_CD='PreAnswer', "
					+"LAST_ANSWER_ID=NULL "
					+"WHERE ID="+str(game['ID']))
		add["type"]=quest[0]['TYPE_CD']
		
		if quest[0]['TYPE_CD']=="С вариантами ответов":
			mes.append(str(quest[0]['QUESTION']).split('|||')[0])
			arr = str(quest[0]['QUESTION']).split('|||')[1].split(';')
			shuffle(arr)
			for ar in arr:
				item = types.KeyboardButton(text=str(ar))
				but.append(item.to_dic())
		else:
			mes.append(str(quest[0]['QUESTION']))
			add["val"]=quest[0]['ADD_FILE']
	else:
		cur.execute("UPDATE T_QUEST_MAIN "
					+"SET STATUS_CD='Default', "
					+"MODE_CD='Default', "
					+"THIS_QUEST_ID=NULL, "
					+"LAST_ANSWER_ID=NULL "
					+"WHERE ID="+str(game['ID']))
		mes.append('Вопросы закончились')
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def userMoveCheck(cur,game,answer):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("select d.ANSWER "
					+"from T_QUEST_DICT d "
					+"WHERE d.ID="+str(game['THIS_QUEST_ID'])
				+" union ALL "
				+"select v.VAL ANSWER "
					+"from T_QUEST_DICT_VAR v "
					+"WHERE v.QUEST_ID="+str(game['THIS_QUEST_ID']))
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
	cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID "
				+"FROM T_QUEST_BEEN")
	rowId = cur.fetchall()[0]['ROW_ID']
	if s==0:
		mes.append("Ответ '"+answer+"' не принят.")
		cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER) VALUES("
						+str(rowId)+","
						+str(game['ID'])+","
						+str(game['THIS_QUEST_ID'])+","
						+"'"+str(answer)+"')")
		cur.execute("UPDATE T_QUEST_MAIN "
						+"SET LAST_ANSWER_ID='"+str(rowId)+"', "
						+"STATUS_CD='PreAnswer' "
						+"WHERE ID="+str(game['ID']))
		if game['TYPE_CD']=="С вариантами ответов":
			arr = str(game['QUESTION']).split('|||')[1].split(';')
			shuffle(arr)
			for ar in arr:
				item = types.KeyboardButton(text=str(ar))
				but.append(item.to_dic())
	else:
		mes.append("Ответ '"+rightAnswer+"' принят.")
		cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER,RESULT) VALUES("
						+str(rowId)+","
						+str(game['ID'])+","
						+str(game['THIS_QUEST_ID'])+","
						+"'"+str(answer)+"','Correct')")
		cur.execute("UPDATE T_QUEST_MAIN "
					+"SET LAST_ANSWER_ID='"+str(rowId)+"', "
					+"STATUS_CD='PostAnswer' "
					+"WHERE ID="+str(game['ID']))
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def editMode(cur,game,new_mode,comment):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET MODE_CD='"+new_mode+"' "
				+"WHERE ID="+str(game['ID']))
	mes.append(comment)
	if new_mode=='Rate':
		for i in range(1,6):
			item = types.KeyboardButton(text=str(i))
			but.append(item.to_dic())
	elif new_mode=='Change Subject':
		pass
	elif new_mode=='Change Type' or new_mode=='Change Add Type':
		cur.execute("""SELECT DISTINCT TYPE_CD 
						FROM V_QUEST_NEXT_DICT d 
						WHERE NOT EXISTS(SELECT 1 
											FROM T_QUEST_BEEN b 
											WHERE b.GAME_ID=%s AND b.QUEST_ID=d.ID AND b.RESULT IS NOT NULL
										) AND TYPE_CD IS NOT NULL""",(game['ID']))
		all_types = cur.fetchall()
		for type in all_types:
			item = types.KeyboardButton(text=str(type['TYPE_CD']))
			but.append(item.to_dic())
	elif new_mode=='Change Block' or new_mode=='Change Add Block':
		cur.execute("""SELECT DISTINCT BLOCK 
						FROM V_QUEST_NEXT_DICT d 
						WHERE NOT EXISTS(SELECT 1 
											FROM T_QUEST_BEEN b 
											WHERE b.GAME_ID=%s AND b.QUEST_ID=d.ID AND b.RESULT IS NOT NULL
										) AND BLOCK IS NOT NULL""",(game['ID']))
		all_types = cur.fetchall()
		for type in all_types:
			item = types.KeyboardButton(text=str(type['BLOCK']))
			but.append(item.to_dic())
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def getAnswer(cur,game):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("SELECT d.ANSWER "
				+"FROM T_QUEST_MAIN m, T_QUEST_DICT d "
				+"WHERE m.THIS_QUEST_ID=d.ID AND m.ID="+str(game['ID']))
	answer = cur.fetchall()
	mes.append(str(answer[0]["ANSWER"]))
	cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID "
				+"FROM T_QUEST_BEEN")
	rowId = cur.fetchall()[0]['ROW_ID']
	cur.execute("INSERT INTO T_QUEST_BEEN(ID,GAME_ID,QUEST_ID,ANSWER,RESULT) VALUES("
								+str(rowId)+","
								+str(game['ID'])+","
								+str(game['THIS_QUEST_ID'])+","
								+"'"+str(answer[0]["ANSWER"])+"',"
								+"'Pass')")
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET LAST_ANSWER_ID='"+str(rowId)+"', "
				+"STATUS_CD='PostAnswer' "
				+"WHERE ID="+str(game['ID']))
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def getComment(cur,game):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("SELECT d.ANSWER,nvl(d.COMMENTS,'Просто так') COMMENTS "
				+"FROM T_QUEST_MAIN m, T_QUEST_DICT d "
				+"WHERE m.THIS_QUEST_ID=d.ID AND m.ID="+str(game['ID']))
	answer = cur.fetchall()
	for ans in answer:
		mes.append(str(ans["COMMENTS"]))
	res['messages']=mes
	cur.execute("UPDATE T_QUEST_BEEN "
					+"SET COMM_FLG=1 "
					+"WHERE ID="+str(game['LAST_ANSWER_ID']))
	res['add']=add
	res['but']=but
	return (res)

def cancelOperation(cur,game):
	res = {}
	mes = []
	but = []
	add = {"type":"","val":""}
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET MODE_CD='Default' "
				+"WHERE ID="+str(game['ID']))
	mes.append("Охрана, отмена")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def firstStepAddQuest(cur,game,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET MODE_CD='Add Answer',"
				+"TEMP_STR='"+text.replace('\'','\'\'')+"' "
				+"WHERE ID="+str(game['ID']))
	mes.append("Введите ответ (варианты строго через точку с запятой и пробел)")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def secondStepAddQuest(cur,game,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET MODE_CD='Add File',"
				+"TEMP_STR_ANS='"+text.replace('\'','\'\'')+"' "
				+"WHERE ID="+str(game['ID']))
	mes.append("Добавьте картинку или аудио")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def thirdStepAddQuest(cur,game,file_type,text,size):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	if size<2**24:
		newQuestion = game['TEMP_STR']
		if file_type=="Текстовый":
			file_text = 'NULL'
			if re.search('^([^;]+;){3}[^;]+$',text):
				file_type = "С вариантами ответов"
				newQuestion += "|||"+text
		else:
			file_text = text
		answers = game['TEMP_STR_ANS'].split('; ')
		cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID "
					+"FROM T_QUEST_DICT")
		rowId = cur.fetchall()[0]['ROW_ID']
		sql_insert_query = """ INSERT INTO T_QUEST_DICT
								(ID,QUESTION,ANSWER,CREATED_BY,TYPE_CD,ADD_FILE) 
								VALUES(%s,%s,%s,%s,%s,%s)"""
		insert_tuple = (rowId, newQuestion, answers[0], game['USER_BOT_ID'], file_type, file_text)
		cur.execute(sql_insert_query,insert_tuple)
		for i in range(1,len(answers)):
			cur.execute("INSERT INTO T_QUEST_DICT_VAR (QUEST_ID,VAL) VALUES("+str(rowId)+",'"+str(answers[i])+"')")
		cur.execute("UPDATE T_QUEST_MAIN "
					+"SET MODE_CD ='Default',"
					+"TEMP_STR=NULL, "
					+"TEMP_STR_ANS=NULL "
					+"WHERE ID="+str(game['ID']))
		mes.append("Спасибо, [Name]. Вопрос добавлен в категорию: "+file_type)
	else:
		mes.append("[Name], файл не должен превышать 16mb. Размер вашего файла: "+str(size/1024/1024))
	res['messages']=mes
	res['add']=add
	res['but']=but

	return (res)

def disputeQuest(cur,game,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	if not game['LAST_ANSWER_ID']:
		cur.execute("SELECT NVL(MAX(ID),0)+1 ROW_ID "
					+"FROM T_QUEST_BEEN")
		rowId = cur.fetchall()[0]['ROW_ID']
		sql_query = """INSERT INTO T_QUEST_BEEN (ID,GAME_ID,QUEST_ID,COMMENTS) VALUES (%s,%s,%s,%s)"""
		qsl_tuple = (rowId,game['ID'],game['THIS_QUEST_ID'],text)
		cur.execute(sql_query,qsl_tuple)
	else:
		rowId = game['LAST_ANSWER_ID']
		sql_query = """UPDATE T_QUEST_BEEN
					SET COMMENTS=case when COMMENTS is null then %s else concat(comments,'; ',%s) end
					WHERE ID=%s """
		qsl_tuple = (text,text,game['LAST_ANSWER_ID'])
		cur.execute(sql_query,qsl_tuple)
	sql_query = """UPDATE T_QUEST_MAIN SET MODE_CD=%s, LAST_ANSWER_ID=%s WHERE ID=%s"""
	qsl_tuple = ('Default',rowId,game['ID'])
	cur.execute(sql_query,qsl_tuple)
	mes.append("Спасибо за отзыв, Ваше мнение очень важно для меня. Вы можете выбрать следующий вопрос или добавить новый")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def rateQuest(cur,game,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	if not re.search('^[1-5]$', str(text)):
		mes.append("Обнаружены неверные символы. Прошу ввести оценка от 1 до 5")
	else:
		cur.execute("UPDATE T_QUEST_MAIN "
					+"SET MODE_CD='Default' "
					+"WHERE ID="+str(game['ID']))
		cur.execute("UPDATE T_QUEST_BEEN "
					+"SET RATE="+str(text)+" "
					+"WHERE ID="+str(game['LAST_ANSWER_ID']))
		mes.append("Спасибо за отзыв. Вы можете выбрать следующий вопрос или добавить новый")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def addComment(cur,game,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	cur.execute("INSERT INTO T_QUEST_COMMENT (USER_BOT_ID,TEXT) VALUES(%s,%s)",(game['USER_BOT_ID'],text))
	mes.append("Спасибо за отзыв, Ваше мнение очень важно для меня.")
	cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD ='Default' WHERE ID=%s",(game['ID']))
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def setSearchSpec(cur,game,type,text):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	text = text.replace("*","'")
	if text.find('LIKE')>0:
		pass
	else:
		text = text.replace(",","','")
	mes.append("Фильтр для вопросов изменен")
	if type == "add":
		cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD ='Default',SEARCH_SPEC=concat(SEARCH_SPEC,' AND ','"+text.replace('\'','\'\'')+"') WHERE ID="+str(game['ID']))
	else:
		cur.execute("UPDATE T_QUEST_MAIN SET MODE_CD ='Default',SEARCH_SPEC='"+text.replace('\'','\'\'')+"' WHERE ID="+str(game['ID']))
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def defaultFunc(cur,game,text="Вы можете выбрать следующий вопрос или добавить новый"):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	mes.append(text)
	cur.execute("UPDATE T_QUEST_MAIN "
				+"SET MODE_CD ='Default',"
				+"TEMP_STR=NULL, "
				+"TEMP_STR_ANS=NULL "
				+"WHERE ID="+str(game['ID']))
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def markToDelete(cur,game):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	if not game['LAST_ANSWER_ID']:
		cur.execute("INSERT INTO T_QUEST_BEEN (GAME_ID,QUEST_ID,MARK_TO_DEL) VALUES ("
											+str(game['ID'])+","+str(game['THIS_QUEST_ID'])+",1)")
	else:
		sql_query = """UPDATE T_QUEST_BEEN
					SET MARK_TO_DEL=1
					WHERE ID=%s """
		qsl_tuple = (game['LAST_ANSWER_ID'])
		cur.execute(sql_query,qsl_tuple)
	mes.append("Спасибо, учту")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)


def main(bot,type,message):
	try:
		if 1==1:
		#if message.from_user.id==394246173:  #ЗАГЛУШКА
			con = pymysql.connect(host='176.36.217.49',port=3307,user='TELEGRAM_BOT',password='!1qaZXsw2@',db='NasDB',charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,connect_timeout=30,max_allowed_packet=1000000000)
			cur = con.cursor()
			try:
				userID = getUser(cur,bot,message)
				tgId=message.from_user.id
				messageText = message.text
				file_size = 0
				if type=="photo":
					raw = message.photo[0].file_id
					file_size = message.photo[0].file_size
					file_info = bot.get_file(raw)
					messageFile = bot.download_file(file_info.file_path)
				elif type=="audio":
					raw = message.audio.file_id
					file_size = message.audio.file_size
					file_info = bot.get_file(raw)
					messageFile = bot.download_file(file_info.file_path)
				if userID>=0:
					game = getGame(cur,userID,bot,tgId)
					func = {
						"Default":{
							"Default":{
								"next":"getNextQuest(cur,game)",#перейти к следующему вопросу
								"add":"editMode(cur,game,'Add Question','Введите вопрос')",#добавить новый вопрос
								"comment":"editMode(cur,game,'Comment','Введите комментарий')",
								"filter":"editMode(cur,game,'Change Filter','Выберите действие')",
								"default":"defaultFunc(cur,game)"#игнорировать
							},
							"Add Question":{#режим добавления вопроса
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"firstStepAddQuest(cur,game,messageText)"#ввод нового вопроса
							},
							"Add Answer":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"secondStepAddQuest(cur,game,messageText)"#ввод нового ответа
							},
							"Comment":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"addComment(cur,game,messageText)"
							},
							"Change Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"reset":"setSearchSpec(cur,game,'new','1=1')",
								"add_filter":"editMode(cur,game,'Add Filter','Выберите критерий')",
								"new_filter":"editMode(cur,game,'New Filter','Выберите критерий')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Add Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Add Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Add Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Add Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Add Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'add',messageText)"
							},
							"New Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Change Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Change Add Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Add Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Add File":{#режим добавления файл
								"cancel":"cancelOperation(cur,game)",#отменить
								"audio":"thirdStepAddQuest(cur,game,'Музыкальный',messageFile,file_size)",
								"photo":"thirdStepAddQuest(cur,game,'Картинка',messageFile,file_size)",
								"default":"thirdStepAddQuest(cur,game,'Текстовый',messageText,0)"
							}
						},
						"PreAnswer":{
							"Default":{
								"next":"getNextQuest(cur,game)",#перейти к следующему вопросу
								"add":"editMode(cur,game,'Add Question','Введите вопрос')",#добавить новый вопрос
								"get":"getAnswer(cur,game)",#узнать ответ
								"dispute":"editMode(cur,game,'Dispute','Введите комментарий')",
								"remind":"{'messages':[game['QUESTION'].split('|||')[0]],'add':{'type':'','val':''},'but':[]}",
								"comment":"editMode(cur,game,'Comment','Введите комментарий')",
								"filter":"editMode(cur,game,'Change Filter','Выберите действие')",
								"default":"userMoveCheck(cur,game,messageText)"#проверить
							},
							"Dispute":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"disputeQuest(cur,game,messageText)"#комментировать вопрос
							},
							"Comment":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"addComment(cur,game,messageText)"
							},
							"Add Question":{#режим добавления вопроса
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"firstStepAddQuest(cur,game,messageText)"#ввод нового вопроса
							},
							"Add Answer":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"secondStepAddQuest(cur,game,messageText)"#ввод нового ответа
							},
							"Change Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"reset":"setSearchSpec(cur,game,'new','1=1')",
								"add_filter":"editMode(cur,game,'Add Filter','Выберите критерий')",
								"new_filter":"editMode(cur,game,'New Filter','Выберите критерий')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Add Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Add Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Add Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Add Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Add Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'add',messageText)"
							},
							"New Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Change Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Change Add Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Add Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Add File":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"audio":"thirdStepAddQuest(cur,game,'Музыкальный',messageFile,file_size)",
								"photo":"thirdStepAddQuest(cur,game,'Картинка',messageFile,file_size)",
								"default":"thirdStepAddQuest(cur,game,'Текстовый',messageText,0)"
							}
						},
						"PostAnswer":{
							"Default":{
								"next":"getNextQuest(cur,game)",#перейти к следующему вопросу
								"add":"editMode(cur,game,'Add Question','Введите вопрос')",#добавить новый вопрос
								"why":"getComment(cur,game)",#почему?
								"rate":"editMode(cur,game,'Rate','Оцените вопрос от 1 до 5')",
								"del":"markToDelete(cur,game)",
								"dispute":"editMode(cur,game,'Dispute','Введите комментарий')",
								"comment":"editMode(cur,game,'Comment','Введите комментарий')",
								"filter":"editMode(cur,game,'Change Filter','Выберите действие')",
								"default":"disputeQuest(cur,game,messageText)"#комментировать вопрос
							},
							"Comment":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"addComment(cur,game,messageText)"
							},
							"Dispute":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"disputeQuest(cur,game,messageText)"#комментировать вопрос
							},
							"Add Question":{#режим добавления вопроса
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"firstStepAddQuest(cur,game,messageText)"#ввод нового вопроса
							},
							"Add Answer":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"secondStepAddQuest(cur,game,messageText)"#ввод нового ответа
							},
							"Rate":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"rateQuest(cur,game,messageText)"#оценка вопроса
							},
							"Change Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"reset":"setSearchSpec(cur,game,'new','1=1')",
								"add_filter":"editMode(cur,game,'Add Filter','Выберите критерий')",
								"new_filter":"editMode(cur,game,'New Filter','Выберите критерий')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Add Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Add Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Add Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Add Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Add Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'add',messageText)"
							},
							"New Filter":{#
								"cancel":"cancelOperation(cur,game)",
								"chtype":"editMode(cur,game,'Change Type','Выберите тип вопросов')",
								"chblock":"editMode(cur,game,'Change Block','Выберите блок вопросов')",
								"chsubj":"editMode(cur,game,'Change Subject','Выберите тему для вопросов')",
								"chdiff":"editMode(cur,game,'Change Difficult','Выберите сложность вопросов')",
								"default":"setSearchSpec(cur,game,'new',messageText)"
							},
							"Change Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'new','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Change Add Type":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(TYPE_CD) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Block":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','upper(BLOCK) in (*'+messageText.upper()+'*)')"
							},
							"Change Add Subject":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"setSearchSpec(cur,game,'add','concat(*,*,upper(TAG_LIST),*,*) LIKE concat(*,*,*'+messageText.upper()+'*,*,*)')"
							},
							"Change Add Difficult":{#
								"cancel":"cancelOperation(cur,game)",#отменить
								"default":"defaultFunc(cur,game,'Данный функционал еще не разработан')"
							},
							"Add File":{#режим добавления ответа
								"cancel":"cancelOperation(cur,game)",#отменить
								"audio":"thirdStepAddQuest(cur,game,'Музыкальный',messageFile,file_size)",
								"photo":"thirdStepAddQuest(cur,game,'Картинка',messageFile,file_size)",
								"default":"thirdStepAddQuest(cur,game,'Текстовый',messageText,0)"
							}
						}
					}
					x = ""
					try:
						x = func[game['STATUS_CD']][game['MODE_CD']][type]
						if mode == 'debug':
							print(game['STATUS_CD'],game['MODE_CD'],type)
					except Exception as f:
						pass
					if len(x)==0:
						result = defaultFunc(cur,game)
					else:
						result = eval(func[game['STATUS_CD']][game['MODE_CD']][type])
					markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
					if game['TYPE_CD']=="С вариантами ответов" and type=="remind" and game['STATUS_CD']=="PreAnswer" and game['MODE_CD']=='Default':
						arr = str(game['QUESTION']).split('|||')[1].split(';')
						shuffle(arr)
						btn = []
						for ar in arr:
							item = types.KeyboardButton(text=str(ar))
							btn.append(item.to_dic())
						markup.keyboard.append(btn)
					if len(result['but'])>0:
						markup.keyboard.append(result['but'])
					cur.execute("SELECT c.*,b.COMM_FLG,b.RATE,b.MARK_TO_DEL "
									+"from T_QUEST_CONFIG c, T_QUEST_MAIN m "
									+"LEFT JOIN T_QUEST_BEEN b ON b.ID=m.LAST_ANSWER_ID "
									+"where m.ID="+str(game['ID'])+" "
									+"AND c.MODE=m.MODE_CD "
									+"AND c.STATE=m.STATUS_CD AND c.BUTTON_NAME is not null "
									+"ORDER BY c.ORDER_BY")
					buttons = cur.fetchall()
					btn = []
					btnrow = []
					r = 1
					for button in buttons:
						if button['COMMAND']=='rate' and button['RATE']:
							pass
						elif button['COMMAND']=='why' and button['COMM_FLG']==1:
							pass
						elif button['COMMAND']=='del' and button['MARK_TO_DEL']==1:
							pass
						else:
							if int(str(button['ORDER_BY'])[0])>r:
								markup.keyboard.append(btnrow)
								btnrow = []
							r = int(str(button['ORDER_BY'])[0])
							itembtn = types.KeyboardButton(text=button['BUTTON_NAME'])
							btnrow.append(itembtn.to_dic())
					if len(btnrow)>0:
						markup.keyboard.append(btnrow)
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
		else:
			bot.send_message(message.from_user.id,"Проводятся технические работы")
	except Exception as e:
		bot.send_message(message.from_user.id,"Ошибка:"+str(e))

def start(mode):
	try:
		startcon = pymysql.connect(host='176.36.217.49',port=3307,user='TELEGRAM_BOT',password='!1qaZXsw2@',db='NasDB',charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,connect_timeout=30,max_allowed_packet=1000000000)
		startcur = startcon.cursor()
		if mode == 'debug':
			bot = telebot.TeleBot("966106908:AAExfZn2rbdcJxyIUDmDUWF31JO7VWkj7NE")
		else:
			bot = telebot.TeleBot("959911904:AAHlPuS8mMdsqQrMmdIG0h5Y9COtyFbCpfs")
		@bot.message_handler(content_types=['audio'])
		def handle_docs_file(message):
			main(bot,'audio',message)
		@bot.message_handler(content_types=['photo'])
		def handle_docs_file(message):
			main(bot,'photo',message)
		@bot.message_handler(content_types=['text'])
		def get_text_messages(message):
			startcur.execute("SELECT DISTINCT BUTTON_NAME,COMMAND FROM T_QUEST_CONFIG")
			cmnds = startcur.fetchall()
			cmd_type = 'default'
			for cmnd in cmnds:
				if message.text==cmnd['BUTTON_NAME']:
					cmd_type=cmnd['COMMAND']
			main(bot,cmd_type,message)
		bot.polling(none_stop=False, interval=1)
	except Exception as e:
		start(mode)

mode = 'default'
if len(sys.argv)>1:
	if sys.argv[1]=='debug':
		mode = 'debug'
	elif sys.argv[1]=='log':
		mode = 'log'
start(mode)