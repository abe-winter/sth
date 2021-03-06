import uuid, re, logging, os
from datetime import datetime, timedelta
import asyncpg
from starlette.templating import Jinja2Templates
from starlette.config import Config

config = Config()
templates = Jinja2Templates(directory='backend/templates') # todo: live on app instead?
POOL = None

def parse_json_iso(raw):
  return datetime.fromisoformat(raw.rstrip('Z'))

def ser_dates(dict_, **transform):
  "prep date + uuid values for ser to json, transform asyncpg Record to dict, apply custom transformations"
  # todo: rename this, test it, doc it; it's doing much more lifting now
  if isinstance(dict_, asyncpg.Record):
    dict_ = dict(dict_)
  for key, val in dict_.items():
    if isinstance(val, datetime):
      dict_[key] = val.isoformat(timespec='seconds') + 'Z'
    elif isinstance(val, uuid.UUID):
      dict_[key] = str(val)
    elif isinstance(val, timedelta):
      dict_[key] = val.total_seconds()
  for key, transformer in transform.items():
    # todo: this should run before the default transforms above
    dict_[key] = transformer(dict_[key])
  return dict_

def prep_serial(item):
  "convert Record to something starlette can jsonify. will mutate inputs on the assumptions they're dicts we made"
  # todo: similar function as ser_dates, pick one. also FastAPI does this out of the box, look into that
  if isinstance(item, asyncpg.Record):
    return prep_serial(dict(item))
  elif isinstance(item, list):
    return [prep_serial(elt) for elt in item]
  elif isinstance(item, dict):
    # note: mutating
    for key, val in item.items():
      if isinstance(val, uuid.UUID):
        item[key] = str(val)
      elif isinstance(val, datetime):
        item[key] = val.isoformat()
    return item
  else:
    return item

def tobytes(raw):
  "helper to return bytes whether bytes or memoryview (postgres / sqlite)"
  return raw if isinstance(raw, bytes) else raw.tobytes()

def quick_norm(raw):
  "hack shortcut to normalize email because I think postmark is choking on the plus"
  user, _pluscode, domain = re.search(r'^([^\+]+)(\+.+)?@(.+)$', raw).groups()
  return f"{user}@{domain}"

async def startup():
  """invoke with `app.on_event("startup")(groundling.util.startup)`"""
  # todo: figure out how to pass concurrency settings in database_url, otherwise settings
  # pylint: disable=global-statement
  global POOL
  POOL = await asyncpg.create_pool(config('DATABASE_URL'), min_size=0, max_size=8)
  if os.environ.get('DEBUG') == '1':
    logging.basicConfig(level=logging.DEBUG)

async def shutdown():
  """invoke with `app.on_event("shutdown")(groundling.util.shutdown)`"""
  await POOL.close()
