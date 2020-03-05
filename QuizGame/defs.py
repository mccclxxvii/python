from telebot import types

def getUser(cur,bot,message):
	userInfo = []
	cur.execute("""SELECT ID,FIRST_NAME FROM T_USER WHERE TELEGRAM_ID=%s""",(message.from_user.id))
	user = cur.fetchall()
	if len(user)==0:
		sql_query = """INSERT INTO T_USER(TELEGRAM_ID,FIRST_NAME,LAST_NAME,NICK_NAME) values (%s,%s,%s,%s)"""
		sql_tuple = (message.from_user.id,message.from_user.first_name,message.from_user.last_name,message.from_user.username)
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
		cur.execute("""SELECT ID,FIRST_NAME FROM T_USER WHERE TELEGRAM_ID=%s""",(message.from_user.id))
		user = cur.fetchall()
		bot.send_message(message.from_user.id,'Привет, '+str(user[0]['FIRST_NAME']))
	else:
		sql_query = """UPDATE T_USER SET FIRST_NAME=%s,LAST_NAME=%s,NICK_NAME=%s WHERE ID=%s"""
		sql_tuple = (message.from_user.first_name,message.from_user.last_name,message.from_user.username,user[0]["ID"])
		cur.execute(sql_query,sql_tuple)
	cur.execute("""SELECT ub.* FROM T_USER_BOT ub,T_BOT b WHERE ub.USER_ID=%s AND ub.BOT_ID=b.ID AND b.NAME='@QuizXIVbot'""",(user[0]["ID"]))
	user_bot = cur.fetchall()
	if len(user_bot)==0:
		cur.execute("""INSERT INTO T_USER_BOT (USER_ID,BOT_ID) SELECT %s,ID FROM T_BOT WHERE NAME='@QuizXIVbot'""",(user[0]["ID"]))
	cur.execute("""SELECT ub.* FROM T_USER_BOT ub,T_BOT b WHERE ub.USER_ID=%s AND ub.BOT_ID=b.ID AND b.NAME='@QuizXIVbot'""",(user[0]["ID"]))
	user_bot = cur.fetchall()
	if user_bot[0]['STATUS_CD']=="LOCKED":
		bot.send_message(message.from_user.id,'Извините, ваша учетная запись заблокирована')
	else:
		userInfo = user_bot[0]
	return(userInfo)
	
def getGame(cur,userID,bot,tgUserId):
	cur.execute("""SELECT q.*,d.QUESTION, d.TYPE_CD,d.VARIANTS FROM T_QUEST_MAIN q LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID WHERE q.USER_BOT_ID=%s""",(userID))
	game = cur.fetchall()
	if len(game)==0:
		cur.execute("""INSERT INTO T_QUEST_MAIN(USER_BOT_ID) VALUES(%s)""",(userID))
		cur.execute("""SELECT q.*,d.QUESTION, d.TYPE_CD, d.VARIANTS FROM T_QUEST_MAIN q LEFT JOIN T_QUEST_DICT d ON q.THIS_QUEST_ID=d.ID WHERE q.USER_BOT_ID=%s""",(userID))
		bot.send_message(tgUserId,'Начнем')
		game = cur.fetchall()
	return(game[0])

def getFile(message,type,bot):
	file_size = 0
	if type=="photo":
		raw = message.photo[0].file_id
		file_size = message.photo[0].file_size
	elif type=="audio":
		raw = message.audio.file_id
		file_size = message.audio.file_size
	file_info = bot.get_file(raw)
	messageFile = bot.download_file(file_info.file_path)
	return (messageFile,file_size)

def setMarkup(cur,markup,game,config):
	cur.execute("""SELECT c.*,b.COMM_FLG,b.RATE,d.ACTIVE_FLAG,ad.ANSWER,ad.QUESTION,ad.ADD_FILE,ad.COMMENTS QUEST_COMM,ad.VARIANTS
		FROM """+config+""" c, T_QUEST_MAIN m 
		LEFT JOIN T_QUEST_BEEN b ON b.ID=m.LAST_ANSWER_ID 
		LEFT JOIN T_QUEST_DICT d ON d.ID=m.THIS_QUEST_ID 
		LEFT JOIN T_QUEST_DICT ad ON ad.ID=m.ADD_QUEST_ID 
		WHERE m.ID=%s AND c.MODE=m.MODE_CD AND c.STATE=m.STATUS_CD AND c.BUTTON_NAME is not null 
		ORDER BY c.ORDER_BY""",(game['ID']))
	buttons = cur.fetchall()
	btn = []
	btnrow = []
	r = 1
	for button in buttons:
		if button['COMMAND']=='rate' and button['RATE']:
			pass
		elif button['COMMAND']=='why' and button['COMM_FLG']==1:
			pass
		elif button['COMMAND']=='del' and button['ACTIVE_FLAG']==0:
			pass
		elif button['COMMAND']=='add answer' and button['ANSWER']:
			pass
		elif button['COMMAND']=='add quest' and button['QUESTION']:
			pass
		elif button['COMMAND']=='add file' and button['ADD_FILE']:
			pass
		elif button['COMMAND']=='add comment' and button['QUEST_COMM']:
			pass
		elif button['COMMAND']=='add vars' and button['VARIANTS']:
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
	return(markup)