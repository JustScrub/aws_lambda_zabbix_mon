
def lambda_handler(event, context):
    todo = event.get('result')
    if todo == 'pass':
        return "passed"
    if todo == 'raise':
        raise Exception('raised')
    if todo == 'timeout':
        from time import sleep
        sleep(5)
    exit(1)