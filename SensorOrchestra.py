from mq131 import MQ131
from mq5 import MQ5, DHTSensor
from dgs import DGSULPSO2
import network
import time
from Azure import Azure
from machine import RTC
import ujson
from grove import Gas
import ntptime



rtc = RTC()
def createFile():
    try:
        f=open('logs.csv', 'r')
        print('logs.csv'+ ' already exists!')
        return 1
    except Exception:
        print("creating filename: ", "logs.csv")
        f=open("logs.csv", 'w')
        #header
        f.write("TIMESTAMP,CO,O3,SO2,NO2,TEMPERATURE,HUMIDITY")
        f.write('\n')
        f.close()
    return 0

def connectWifi():
    wifi = network.WLAN(network.STA_IF)
    connected = False
    if not wifi.isconnected():
        wifi.active(True)
        wifi.connect("Maria's iPhone", "mafer1234")
        #esperamos unos 6 segundos para autenticar
        time.sleep(6)
        if wifi.isconnected():
            print("Connected to Internet!")
            ntptime.settime()

            connected = True
        else:
            print("Wifi error")
    else:
        connected = True

        
    print("Local time:%s" %str(time.localtime()))
    return connected


print("Setting up everything!")
connected = connectWifi()
print("Connection to Internet", connected)
g = Gas()

mq5 = MQ5()
tempSensor = DHTSensor()
mq131 = MQ131()
dgs = DGSULPSO2()

#Si no hay comunicacion, no inicializamos Azure
if connected:
    IoTPublisher = Azure()
    IoTPublisher.configure_vars()
    IoTPublisher.configure_mqtt()
    IoTPublisher.connect()
    IoTPublisher.subscribe_topic()
    IoTPublisher.telemetry_topic()
else:
    IoTPublisher = None
    
time.sleep(10)

#set R0 MQ5
mq5.get_resistance()
tempSensor.get_temp_hum()
print("Initial temp", tempSensor.temp, tempSensor.hum)
mq5.get_corrected_r0(tempSensor.temp, tempSensor.hum)
print("SET R0 for MQ5", mq5.r0)


#set R0 Mq131
mq131.read()
mq131.resistance()
mq131.get_corrected_r0(tempSensor.temp, tempSensor.hum)
print('SET R0 for MQ131', mq131.r0)


# set DGS SO2
dgs = DGSULPSO2()
dgs.start()

#set MICS
#g.display_eeprom()
createFile()

f = open('logs.csv', "a")
count = 0

try:
    while True:
        
        if tempSensor.get_temp_hum() != -1:
            mq5.get_resistance()
            mq5.get_corrected_ppm(tempSensor.temp, tempSensor.hum)
            print("Corrected CO PPM: ", mq5.ppm)

            mq131.read()
            mq131.resistance()
            mq131.get_corrected_ppm(tempSensor.temp, tempSensor.hum)
            print('Corrected O3 PPM', mq131.ppm)
        else:
            mq5.get_resistance()
            mq5.get_ppm()
            print("CO PPM: ", mq5.ppm)


        dgs.get_reading()
        dgs.parse()

        g.gas_dump()
            
        # YYYY-MM-DD HH:MM
        if rtc.datetime()[5] < 10:
            timestamp = str(rtc.datetime()[0]) + '-' + str(rtc.datetime()[1]) + '-' +  str(rtc.datetime()[2]) + ' ' + str(rtc.datetime()[4]) + ':' + "0" + str(rtc.datetime()[5])
        else:
            timestamp = str(rtc.datetime()[0]) + '-' + str(rtc.datetime()[1]) + '-' +  str(rtc.datetime()[2]) + ' ' + str(rtc.datetime()[4]) + ':' + str(rtc.datetime()[5])
        line = timestamp + ',' + str(mq5.ppm) + ',' + str(mq131.ppm) + ',' + str(dgs.ppm) + ',' + str(g.no2) + ',' + str(tempSensor.temp) + ',' + str(tempSensor.hum)
        print("MICS CO", g.co)
        mqttStruct = {
            "TIMESTAMP": timestamp, 
            "deviceId": 's01', 
            "CO": mq5.ppm, 
            "SO2": dgs.ppm, 
            "O3": mq131.ppm, 
            "NO2": g.no2, 
            "temperature": tempSensor.temp, 
            "humidity": tempSensor.hum
        }
        mqttStruct = ujson.dumps(mqttStruct)
        IoTPublisher.send(mqttStruct)
        f.write(line)
        f.write('\n')
        
        if count > 150:
            f.close()
        else:
            count += 1
        time.sleep(65)

except KeyboardInterrupt:
    dgs.stop()
    time.sleep(5)
    print('Graceful exit.')
