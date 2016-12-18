import sqlite3
import getopt
import sys
import requests
import pprint
import json

def createTable():
	conn = sqlite3.connect('vroom.db')
	c = conn.cursor()

	#create table
	q = """
		CREATE TABLE IF NOT EXISTS edmunds
		(vin text, make text, model text, year integer, body_type text, 
			certifiedUsedPrice real, usedPrivateParty real, usedTmvRetail real, 
			usedTradeIn real)
		"""
	c.execute(q)

	#commit changes
	conn.commit()

	#close connection
	conn.close()


def dropTable():
	conn = sqlite3.connect('vroom.db')
	c = conn.cursor()

	#create table
	q = """DROP TABLE IF EXISTS edmunds"""
	c.execute(q)

	#commit changes
	conn.commit()

	#close connection
	conn.close()


def insert_row(sql_input):
	"""take dict on inputs and insert them into the table"""
	#make sure table exists
	createTable()

	#convert empty values to NULL
	for key, val in sql_input.iteritems():
		if val == "":
			val = "NULL"

	#connect and insert
	conn = sqlite3.connect('vroom.db')
	c = conn.cursor()
	q = """
		INSERT INTO edmunds (vin, make, model, year, body_type, certifiedUsedPrice, 
			usedPrivateParty, usedTmvRetail, usedTradeIn)
		VALUES ('%s','%s', '%s', %s, '%s', %s, %s, %s, %s)
		""" % (sql_input['vin'], sql_input['make'], sql_input['model'], \
			   sql_input['year'], sql_input['body_type'], \
			   sql_input['certifiedUsedPrice'], sql_input['usedPrivateParty'], \
			   sql_input['usedTmvRetail'], sql_input['usedTradeIn'])
	c.execute(q)

	#commit changes
	conn.commit()

	#close connection
	conn.close()


def select(where="1=1"):
	"""take dict on inputs and insert them into the table"""
	conn = sqlite3.connect('vroom.db')
	c = conn.cursor()
	#select contents of new table
	q = """
		SELECT *
		FROM edmunds
		WHERE %s""" % (where)

	for row in c.execute(q):
		print row

def checkVIN(vin):
	"""take dict on inputs and insert them into the table"""
	exists = False

	conn = sqlite3.connect('vroom.db')
	c = conn.cursor()
	#select contents of new table
	q = """
		SELECT vin
		FROM edmunds
		WHERE vin = '%s'""" % (vin)
	
	count = 0 
	try:
		for row in c.execute(q):
			count += 1
		if count > 0:
			exists = True
	except sqlite3.OperationalError:
		createTable()	#table does not exist... so make it

	return exists

def getVinMileage(vin, mileage):
	"""Get data for a specific vin and mileage"""
	#Double check data for the vin does not already exist
	if checkVIN(vin) == False:
		#if it does not exist, query the api
		payload = {"api_key" : "kdj6mj65bapsf8wzc936j36u"}
		url = "https://api.edmunds.com/api/vehicle/v2/vins/"+vin

		r = requests.get(url, params=payload)
		response = r.json()
		#check and only load data for successful response
		if r.status_code not in (200, 202):
			print str(r.status_code), " | \n", response
		else:
			#put data for sql in variables
			sql_input = {"vin" : vin}
			##make
			try:
				sql_input["make"] = response["make"]["name"]
			except:
				print "Error: no [make][name] in response"
				sql_input["make"] = ""
			##model
			try:
				sql_input["model"] = response["model"]["id"]
			except:
				print "Error: no [model][id] or [name] in response"
				sql_input["model"] = ""
			##year
			try:
				sql_input["year"] = response["years"][0]["year"] #just take the first year
			except:
				print "Error: no [years][year] in response"
				sql_input["year"] = ""
			##body type
			try:
				#sql_input["primaryBodyType"] = response["categories"]["primaryBodyType"]
				sql_input["body_type"] = response["years"][0]["styles"][0]["submodel"]["body"]
			except:
				print "Error: no [categories][primaryBodyType] in response"
				sql_input["body_type"] = ""

			#Run another API call for the certifiedUsedPrice
			#will need: styleid, condition, mileage, zip
			try:
				styleid = response["years"][0]["styles"][0]["id"]
				condition = "Clean" 	#static b/c I could not find this value via VIN
				zipcode = "90019"		#static for reason above
			except:
				print "could not retrieve syleid"

			payload = {"api_key" : "kdj6mj65bapsf8wzc936j36u", 
					   "styleid" : styleid,
					   "fmt" : "json",
					   "mileage" : str(int(mileage)),
					   "condition" : condition,
					   "zip" : zipcode}
			url = "https://api.edmunds.com/v1/api/tmv/tmvservice/calculateusedtmv"
			r = requests.get(url, params=payload)
			response = r.json()

			##certified used price
			try:
				sql_input["certifiedUsedPrice"] = response["tmv"]["certifiedUsedPrice"]
			except:
				print "Error: no [tmv][certifiedUsedPrice] in response"
				sql_input["usedPrivateParty"] = ""
			##totals with options prices (assumes you will have all or none)
			try:
				sql_input["usedPrivateParty"] = response["tmv"]["totalWithOptions"]["usedPrivateParty"]
				sql_input["usedTmvRetail"] = response["tmv"]["totalWithOptions"]["usedTmvRetail"]
				sql_input["usedTradeIn"] = response["tmv"]["totalWithOptions"]["usedTradeIn"]
			except:
				print "Error: no [tmv][totalWithOptions][<price>] in response"
				sql_input["usedPrivateParty"] = ""
				sql_input["usedTmvRetail"] = ""
				sql_input["usedTradeIn"] = ""

			insert_row(sql_input)
	else:
		print vin, "already exists in db"

def getCSV(csvfile):
	"""Get data for a csv with the following headers:
		vin, make, model, year, trim, style, odometer
		Note: odometer = mileage"""
	import csv
	filepath = "./" + str(csvfile)
	with open(filepath, 'rb') as infile:
		reader = csv.reader(infile)
		header = reader.next()
		for row in reader:
			vin = row[0]
			mileage = row[6]
			getVinMileage(vin, mileage)


def help():
	"""help for the get opts"""
	print """
	-h or --help: show help

	Option 1:
	-v or --vim (required): vim
	-m or --mileage (required): mileage

	Option 2:
	-c or --csv (required): name of csv file"""


def main():
	"""run everything with cli options"""
	#expect either "vin/mileage" or "csv" as required inputs, but not both
	option_style = ""
	#get command line options and handle errors
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hv:m:", ["help", "vin=", "mileage="])
		option_style = "vin/mileage"
	except getopt.GetoptError as err:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:", ["help", "csv="])
			option_style = "csv"
		except getopt.GetoptError as err2:
			print "vin/mileage option: " + str(err)
			print "csv option: "  + str(err2)
			help()
			sys.exit(2)

	if option_style == "vin/mileage":
		vin = ""
		mileage = 0.0
		for o, a in opts:
			if o in ("-h", "--help"):
				help()
				sys.exit()
			elif o in ("-v", "--vin"):
				vin = str(a)
			elif o in ("-m", "--mileage"):
				mileage = float(a)
			else:
				assert False, "unhandled option"
		print "vin = " + str(vin)
		print "mileage = " + str(mileage)

		#run script to get data
		getVinMileage(vin, mileage)
	elif option_style == "csv":
		csv = ""
		for o, a in opts:
			if o in ("-h", "--help"):
				help()
				sys.exit()
			elif o in ("-c", "--csv"):
				csv = str(a)
			else:
				assert False, "unhandled option"
		print "csv = " + str(csv)
		
		#run script to get data
		getCSV(csv)
	else:
		print "Not a recognized option" 	#wont happen unless strings dont match
	
	

if __name__ == "__main__":
    main()