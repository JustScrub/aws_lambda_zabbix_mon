import json

def ret_json(constr):
    return lambda *args, **kwargs: json.dumps(constr(*args, **kwargs))

@ret_json
def logon(user="Admin",passwd="zabbix"):
    return {
        "jsonrpc":"2.0",
        "method":"user.login",
        "params":{
            "username": user,
            "password": passwd
            },
        "id":1
        }

@ret_json
def logout(token):
    return {
        "jsonrpc":"2.0",
        "method":"user.logout",
        "params":[],
        "auth": token,
        "id":1
        }

@ret_json
def host_create():
    pass

