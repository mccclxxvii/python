import re
from telebot import types
from difflib import SequenceMatcher
from random import shuffle

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
			mes.append(str(quest[0]['QUESTION']))
			arr = str(quest[0]['VARIANTS']).split(';')
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
		mes.append("Неправильно :( Ответ '"+answer+"' не принят.")
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
			arr = str(game['VARIANTS']).split(';')
			for ar in arr:
				item = types.KeyboardButton(text=str(ar))
				but.append(item.to_dic())
	else:
		mes.append("Правильно!!! Ответ '"+rightAnswer+"' принят.")
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
	cur.execute("""UPDATE T_QUEST_MAIN SET MODE_CD='Default',ADD_QUEST_ID=NULL WHERE ID=%s""",(game['ID']))
	if game["ADD_QUEST_ID"]:
		cur.execute("""DELETE FROM T_QUEST_DICT WHERE ID=%s""",(game["ADD_QUEST_ID"]))
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
				text = text.split(';')
				shuffle(text)
				text = text[0]+';'+text[1]+';'+text[2]+';'+text[3]
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
	cur.execute("""UPDATE T_QUEST_DICT SET ACTIVE_FLAG=0 WHERE ID=%s """,(game['THIS_QUEST_ID']))
	mes.append("Спасибо, учту")
	res['messages']=mes
	res['add']=add
	res['but']=but
	return (res)

def addNewQuestion(cur,game,text,size,field,file_type='Текстовый'):
	res = {}
	add = {"type":"","val":""}
	mes = []
	but = []
	if not game['ADD_QUEST_ID']:
		cur.execute("""SELECT NVL(MAX(ID),0)+1 ROW_ID FROM T_QUEST_DICT""")
		rowId = cur.fetchall()[0]['ROW_ID']
		cur.execute("""INSERT INTO T_QUEST_DICT (ID,ACTIVE_FLAG) VALUES(%s,%s)""",(rowId,0))
		cur.execute("""UPDATE T_QUEST_MAIN SET ADD_QUEST_ID=%s WHERE ID=%s""",(rowId,game["ID"]))
	else:
		rowId = game['ADD_QUEST_ID']
	if field=="ALL":
		cur.execute("""SELECT * FROM T_QUEST_DICT WHERE ID=%s""",(rowId))
		new_quest = cur.fetchall()[0]
		if not new_quest['QUESTION'] or not new_quest['ANSWER']:
			mes.append("Не заполнены обязательные поля (Вопрос и ответ)")
		else:
			cur.execute("""UPDATE T_QUEST_DICT SET ACTIVE_FLAG = 1 WHERE ID=%s""",(rowId))
			mes.append("Спасибо, [Name]. Вопрос добавлен в категорию: "+new_quest['TYPE_CD'])
			cur.execute("""UPDATE T_QUEST_MAIN SET MODE_CD='Default',ADD_QUEST_ID=NULL WHERE ID=%s""",(game["ID"]))
	else:
		success = True
		if field == "QUESTION":
			cur.execute("""UPDATE T_QUEST_DICT SET QUESTION =%s WHERE ID=%s""",(text,rowId))
		elif field == "ANSWER":
			answers = text.split('; ')
			cur.execute("""DELETE FROM T_QUEST_DICT_VAR WHERE QUEST_ID=%s""",(rowId))
			for i in range(1,len(answers)):
				cur.execute("""INSERT INTO T_QUEST_DICT_VAR (QUEST_ID,VAL) VALUES(%s,%s)""",(rowId,answers[i]))
			cur.execute("""UPDATE T_QUEST_DICT SET ANSWER =%s WHERE ID=%s""",(answers[0],rowId))
		elif field == "COMMENTS":
			cur.execute("""UPDATE T_QUEST_DICT SET COMMENTS =%s WHERE ID=%s""",(text,rowId))
		elif field == "ADD_FILE":
			if size<2**24:
				cur.execute("""UPDATE T_QUEST_DICT SET ADD_FILE =%s,TYPE_CD=%s WHERE ID=%s""",(text,file_type,rowId))
			else:
				success = False
				mes.append("[Name], файл не должен превышать 16mb. Размер вашего файла: "+str(size/1024/1024))
		elif field == "VARIANTS":
			text = text.split(';')
			shuffle(text)
			text = text[0]+';'+text[1]+';'+text[2]+';'+text[3]
			cur.execute("""UPDATE T_QUEST_DICT SET VARIANTS =%s,TYPE_CD=%s WHERE ID=%s""",(text,file_type,rowId))
		if success:
			mes.append("Поле "+field+" обновлено")
			cur.execute("""UPDATE T_QUEST_MAIN SET MODE_CD='Add' WHERE ID=%s""",(game["ID"]))
	res['messages']=mes
	res['add']=add
	res['but']=but

	return (res)