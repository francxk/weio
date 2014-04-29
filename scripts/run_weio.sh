#!/bin/sh

# Launching WeIO application, if application crashes WeIO will rerun automaticaly
# On each exit from application script checks if an update is needed
# Update process once decompressed new version to RAM exits application, script will
# do the rest of moving files to good target

WIFI_READY=0

# Function to check wifi state
check_wifi()
{
    DELAY=5
    COUNTER=0
        
    # Wait for WiFi interface to appear
    while [ ! -e /sys/class/net/wlan0/operstate ]; do
        # WiFi is still down. Wait a bit.
        sleep 1
        COUNTER=`expr $COUNTER + 1`
        if [ $COUNTER -ge $DELAY ]; then
           echo "WiFi interface is DOWN"
           return
        fi
    done
    
    # Reset counter
    COUNTER=0
    while [  $COUNTER -lt $DELAY ]; do
    	OPERSTATE=`cat /sys/class/net/wlan0/operstate`
        if [ "$OPERSTATE" != "up" ]; then
            echo "WiFi is $OPERSTATE. Waiting..."
            sleep 1
            COUNTER=`expr $COUNTER + 1`
        else
            break
        fi
    done

    if [ $COUNTER -ge $DELAY ]; then
        WIFI_READY=0
    else
    	echo "WiFi is READY"
        WIFI_READY=1
    fi
}


###
# Loop forever - restart WeIO if it exits
###
cd /weio

# If led_blink is not running - start it
if [ -z "$(ps | grep  "[l]edBlink.py")" ]; then
    echo "Starting ledBlink.py..."
    /etc/init.d/led_blink start
fi

# First check if WiFi is UP
check_wifi

while [ $WIFI_READY -ne 1 ]; do
    echo "WiFi network is not ready. Switching to RESCUE mode."

    # We did not connect even after whole delay expired
    # Something went wrong - got to RESCUE
    /weio/scripts/wifi_set_mode.sh rescue

    # Re-check WiFi
    check_wifi
done

# Restart avahi
# First kill it
avahi-daemon -k
# The daemonize it
avahi-daemon -D

echo "===> STARTING THE SERVER"

# And start WeIO
./weioServer.py > /dev/null

### WE HAVE EXITED SERVER - CHECK OUT WHY ###
echo "===> EXITED SERVER"
    
if grep -q '"kill_flag": "YES"' /weio/config.weio
then
    echo "Found kill flag"

    if [ -d "/tmp/weio" ]; then
      echo "Running pre install procedure"
      sh /tmp/weio/scripts/pre_install.sh
      echo "Deleting old WeIO"
      rm -r /weio
      echo "Moving from RAM to target place new WeIO"
      mv /tmp/weio /weio
      echo "Running post install procedure"
      sh /weio/scripts/post_install.sh
      echo "Installation done!"
    fi
fi

# And here we go again!
/etc/init.d/weio_run restart
