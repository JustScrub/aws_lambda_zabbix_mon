"""
Basic Metric Stream handler used to monitor AWS Lambda functions in Zabbix.    
Can handle any type of AWS/Lambda metric and statistic as configured via project configuration.    
First discovers AWS Lambda functions in Zabbix.    
Then translates each metric and statistic pair to a Zabbix item and 
pushes the value of that AWS metric-statistic to the Zabbix item via the Zabbix Sender (aka Trapper) protocol.    
Cannot transform metric-statistic values to different values to be pushed to Zabbix. Only sends AWS values directly to Zabbix items.

Contribute:
    - enable value transfromation by making a differnet handle and 
      ideally changing utils/utils.py `zbx_mass_item_packet` function to support such transformations
"""