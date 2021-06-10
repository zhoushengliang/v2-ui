import calendar
import logging
import threading
from datetime import datetime, timedelta
from threading import Timer

import requests

from init import db
from util import config, v2_util
from util.schedule_util import schedule_job
from v2ray.models import Inbound

# __lock = threading.Lock()
__v2_config_changed = True


def v2_config_change(func):
    def inner(*args, **kwargs):
        global __v2_config_changed
        result = func(*args, **kwargs)
        __v2_config_changed = True
        return result
    inner.__name__ = func.__name__
    return inner


def check_v2_config_job():
    global __v2_config_changed
    if __v2_config_changed:
        # with __lock:
        v2_config = v2_util.gen_v2_config_from_db()
        v2_util.write_v2_config(v2_config)
        __v2_config_changed = False


def traffic_job():
    if not v2_util.is_running():
        return
    try:
        traffics = v2_util.get_inbounds_traffic()
        if not traffics:
            return
        for traffic in traffics:
            upload = int(traffic.get('uplink', 0))
            download = int(traffic.get('downlink', 0))
            tag = traffic['tag']
            Inbound.query.filter_by(tag=tag).update({'up': Inbound.up + upload, 'down': Inbound.down + download})
        db.session.commit()
    except Exception as e:
        logging.warning(f'traffic job error: {e}')


def total_traffic_thredsold_job():
    if not v2_util.is_running():
        return
    total_traffic_thredsold = config.get_total_traffic_thredsold()
    if total_traffic_thredsold == 0:
        return
    try:
        inbs = Inbound.query.all()
        total_traffic = 0
        # GB to B
        total_traffic_thredsold = total_traffic_thredsold * 1024 * 1024 * 1024
        for inb in inbs:
            total_traffic = total_traffic + inb.down + inb.up
        logging.info('total_traffic ' + total_traffic + ' total_traffic_thredsold ' + total_traffic_thredsold)
        if total_traffic > total_traffic_thredsold:
            v2_util.stop_v2ray()
    except Exception as e:
        logging.warning(f'total_traffic_thredsold job error: {e}')


def reset_traffic_job():
    def run_next():
        now = datetime.now()
        next_day = now.date() + timedelta(days=1)
        next_time = datetime.combine(next_day, datetime.min.time())
        Timer((next_time - now).seconds + 5, reset_traffic_job).start()

    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    end_day = calendar.monthrange(int(year), int(month))[1]
    reset_day = config.get_reset_traffic_day()
    if end_day < reset_day:
        reset_day = end_day
    if day == reset_day:
        if config.is_traffic_reset():
            run_next()
            return
        Inbound.query.update({'up': 0, 'down': 0})
        db.session.commit()
        config.update_setting_by_key('is_traffic_reset', 1)
    else:
        config.update_setting_by_key('is_traffic_reset', 0)
    run_next()


def check_v2ay_alive_job():
    if not v2_util.is_running():
        v2_util.restart(True)


def init():
    schedule_job(check_v2_config_job, config.get_v2_config_check_interval())
    schedule_job(traffic_job, config.get_traffic_job_interval())
    schedule_job(total_traffic_thredsold_job, config.get_traffic_job_interval())
    schedule_job(check_v2ay_alive_job, 40)
    reset_day = config.get_reset_traffic_day()
    if reset_day <= 0:
        return
    now = datetime.now()
    next_day = now.date() + timedelta(days=1)
    next_day = datetime.combine(next_day, datetime.min.time())

    Timer((next_day - now).seconds + 5, reset_traffic_job).start()
