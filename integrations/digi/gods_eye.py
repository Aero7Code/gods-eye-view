"""Digi adapter to God's Eye View's loopback MCP API and embedded globe."""
import datetime
import http.client
import json
import math
import re
import threading
import time
from .web_fetch import PublicHTTPS

PORT = 4173
BASE_URL = 'http://127.0.0.1:4173'
TOOL = {'type':'function','function':{'name':'gods_eye','description':"Control and read the live God's Eye View globe in Digi's sidebar. Use operation=catalog for available queries and their exact schemas; operation=query with tool and arguments_json to query aircraft, tracks, route metadata, ships, satellites, earthquakes, cameras, infrastructure or a situation brief. show_in_gods_eye_view frames a place (arguments {area:{place:'Paris, France'}}) or applies a returned view. operation=flight with flight retrieves current position, recent track, route and a clearly labeled remaining-distance/time estimate. operation=state reads Digi's selected view. Missing/stale feeds must be reported; never invent a location or ETA.",'parameters':{'type':'object','properties':{'operation':{'type':'string','enum':['catalog','query','flight','state']},'tool':{'type':'string'},'arguments_json':{'type':'string'},'flight':{'type':'string'}},'required':['operation'],'additionalProperties':False}}}

class GodsEye:
    def __init__(self):
        self.lock=threading.Lock()
        self.selected=None
        self.latest_result=None
        self.observed_view=None
        self.revision=0
        self.catalog_cache=None

    def rpc(self, method, params=None, job=None):
        if job and job['stop'].is_set():raise ValueError('Request stopped')
        conn=http.client.HTTPConnection('127.0.0.1',PORT,timeout=75)
        if job:job['connection']=conn
        try:
            conn.request('POST','/mcp',json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}),{'Content-Type':'application/json','Accept':'application/json'})
            response=conn.getresponse()
            raw=response.read(3000001)
            if response.status!=200 or len(raw)>3000000:raise ValueError('God’s Eye View API did not return a usable response')
            payload=json.loads(raw)
            if 'error' in payload:raise ValueError(payload['error'].get('message','God’s Eye View API error'))
            if job and job['stop'].is_set():raise ValueError('Request stopped')
            return payload['result']
        except (OSError,http.client.HTTPException) as exc:
            raise ValueError('God’s Eye View is unavailable; check digi-gods-eye.service') from exc
        finally:
            conn.close()
            if job and job.get('connection') is conn:job['connection']=None

    def catalog(self, job=None):
        if self.catalog_cache is None:
            self.catalog_cache=[t for t in self.rpc('tools/list',job=job)['tools'] if t['name']!='panel_request']
        return self.catalog_cache

    def query(self, name, arguments, job=None):
        if name not in {t['name'] for t in self.catalog(job)}:raise ValueError('Unknown God’s Eye View query')
        if not isinstance(arguments,dict):raise ValueError('Query arguments must be an object')
        result=self.rpc('tools/call',{'name':name,'arguments':arguments},job)
        if result.get('isError'):raise ValueError(' '.join(c.get('text','') for c in result.get('content',[])))
        data=result.get('structuredContent')
        summary=''
        for item in result.get('content',[]):
            if item.get('type')=='text':
                try:
                    obj=json.loads(item['text'])
                    if isinstance(obj,dict):
                        summary=obj.get('summary',summary)
                        if data is None:data=obj.get('data',obj)
                except ValueError:summary=item['text']
        data=data or {}
        if isinstance(data,dict) and isinstance(data.get('view'),dict):
            with self.lock:
                self.revision+=1
                self.selected={'revision':self.revision,'view':data['view'],'summary':summary,'tool':name,'observed_at':time.time()}
        answer={'summary':summary,'data':data}
        with self.lock:self.latest_result=answer
        return answer

    def state(self):
        with self.lock:return {'base_url':BASE_URL,'selected':self.selected,'revision':self.revision,'latest_result':self.latest_result,'observed_view':self.observed_view}

    def observe(self, camera):
        if not isinstance(camera,dict):raise ValueError('Invalid camera observation')
        bounds={'lat':(-90,90),'lon':(-180,180),'altitude_m':(-1000,1000000000),'heading_deg':(-360,360),'pitch_deg':(-90,90)}
        result={}
        for key,(low,high) in bounds.items():
            value=camera.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid camera observation')
            result[key]=value
        with self.lock:self.observed_view={'camera':result,'observed_at':time.time(),'source':'God’s Eye View browser camera'}
        return {'ok':True}

    def run(self, operation, tool='', arguments_json='{}', flight='', job=None):
        if operation=='catalog':return {'tools':self.catalog(job)}
        if operation=='state':return self.state()
        if operation=='flight':
            result=self.flight(flight,job)
            result['answer']=render(result)
            with self.lock:self.latest_result=result
            return result
        if operation=='query':return self.query(tool,json.loads(arguments_json),job)
        raise ValueError('Unknown operation')

    def flight(self, flight, job=None):
        callsign=normalize_flight(flight)
        try:found=self.query('find_aircraft',{'callsign':callsign},job)
        except ValueError as exc:found={'summary':str(exc),'data':{'rows':[],'feeds':[]}}
        rows=found['data'].get('rows',[])
        # Targeted lookup avoids a stale or regional anonymous global snapshot.
        if not rows or found['data'].get('stale_feeds'):
            try:
                targeted=targeted_flight(callsign,job)
                if targeted['data']['rows']:
                    found=targeted
                    rows=found['data']['rows']
                    if len(rows)==1:
                        row=rows[0]
                        view={'camera':{'lat':row['lat'],'lon':row['lon'],'altitude_m':50000,'heading_deg':0,'pitch_deg':-90},'layers':['flights'],'follow':{'kind':'aircraft','id':row['id']},'annotations':[]}
                        found['data']['view']=view
                        self.query('show_in_gods_eye_view',{'view':view},job)
            except ValueError as exc:
                found['data']['targeted_lookup_error']=str(exc)
        result={'summary':found['summary'],'callsign':callsign,'positions':found['data'],'route':None,'track':None,'estimate':None,'limitations':[]}
        if len(rows)!=1:
            try:result['route']=self.query('get_aircraft_info',{'callsign':callsign},job)['data']
            except ValueError as exc:result['limitations'].append(str(exc))
            result['limitations'].append('No unique currently reported aircraft; no current location or ETA can be confirmed.')
            return result
        row=rows[0]
        for name,args,key in [('get_aircraft_info',{'icao24':row['id'],'callsign':callsign},'route'),('get_aircraft_track',{'icao24':row['id']},'track')]:
            try:result[key]=self.query(name,args,job)['data']
            except ValueError as exc:result['limitations'].append(str(exc))
        dest=(result['route'] or {}).get('route',{} ) or {}
        result['estimate']=remaining_estimate(row,dest.get('destination'),found['data'])
        points=(result.get('track') or {}).get('points',[])
        origin=dest.get('origin') or {}
        if points and type(points[0].get('altitude_m')) in (int,float) and points[0]['altitude_m']<500:
            departure=remaining_estimate({'lat':points[0].get('lat'),'lon':points[0].get('lon'),'last_contact':row.get('last_contact'),'speed_mps':0},origin,{})
            if departure and departure['straight_line_km']>100:
                result['estimate']=None
                result['limitations'].append('Route metadata conflicts with the observed low-altitude departure track; the current destination and arrival estimate cannot be confirmed.')
        # Restore the freshest location after the historical-track query.
        view=found['data'].get('view')
        if view:
            view={**view,'camera':{**view['camera'],'lat':row['lat'],'lon':row['lon']}}
            if len(points)>=2:
                sample=[points[round(i*(len(points)-1)/11)] for i in range(12)] if len(points)>12 else points
                view['annotations']=[{'type':'route','label':'Recent observed track (simplified)','points':[{'latitude':p['lat'],'longitude':p['lon']} for p in sample]}]
            try:self.query('show_in_gods_eye_view',{'view':view},job)
            except ValueError as exc:result['limitations'].append(str(exc))
        result['limitations'].append('Route metadata is not a confirmed flight plan. Recent track is observed history, not the future path. Time estimate assumes straight-line travel at current ground speed and excludes turns, weather and landing; it is not an airline ETA.')
        return result


def normalize_flight(value):
    value=str(value).strip().upper()
    value=re.sub(r'^(?:FLIGHT\s+)', '', value)
    value=re.sub(r'\s+', '',value)
    value=value.replace('SOUTHWESTAIRLINES','SWA').replace('SOUTHWEST','SWA')
    if re.fullmatch(r'WN\d{1,4}',value):value='SWA'+value[2:]
    if not re.fullmatch(r'[A-Z]{2,3}\d{1,4}[A-Z]?',value):raise ValueError('Give an airline flight number or callsign, such as Southwest 2456, WN2456 or SWA2456. A2456 is ambiguous.')
    return value


def remaining_estimate(row, destination, evidence):
    if not destination:return None
    values=[row.get('lat'),row.get('lon'),destination.get('lat'),destination.get('lon')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):return None
    try:
        age=time.time()-datetime.datetime.fromisoformat(row['last_contact'].replace('Z','+00:00')).timestamp()
    except (KeyError,ValueError,TypeError):return None
    if not -30<=age<=120 or any(f.get('freshness')=='stale' for f in evidence.get('feeds',[])):return None
    lat1,lon1,lat2,lon2=map(math.radians,values)
    h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    distance=6371*2*math.asin(math.sqrt(min(1,h)))
    speed=row.get('speed_mps')
    return {'straight_line_km':round(distance,1),'straight_line_miles':round(distance*.621371,1),'estimated_minutes':round(distance*1000/speed/60,1) if type(speed) in (int,float) and speed>0 and not row.get('on_ground') else None,'position_age_seconds':round(age,1),'method':'great-circle distance / current ground speed; not scheduled or predicted arrival'}


def request(text):
    text=re.sub(r'(?i)^\s*(?:hey\s+)?digi[,!: ]*','',text).strip()
    if re.search(r'(?i)\b(write|implement|build|translate|fictional)\b',text):return None
    match=re.fullmatch(r'(?is)(?:show me|show|take me to|zoom (?:in )?to|look at)\s+(.{2,160}?)[.!?]*',text)
    if match and not re.search(r'(?i)\b(flight|south\s*west|SWA\d{1,4}|WN\d{1,4}|screen|code|settings|memory|image|picture|how|your|my|research|model|status|tools|task|brain|voice|files|conversation)\b',match[1]):
        place=re.sub(r'(?i)\bparris\b','Paris',match[1])
        place=re.sub(r'(?i)\bfrans\b','France',place)
        return {'operation':'query','tool':'show_in_gods_eye_view','arguments_json':json.dumps({'area':{'place':place},'layers':['flights']})}
    if re.search(r'(?i)\b(flight|south\s*west|SWA\d{1,4}|WN\d{1,4})\b',text):
        number=re.search(r'(?i)\b(?:SWA|WN)\s*(\d{1,4})\b',text)
        if not number and re.search(r'(?i)south\s*west',text):number=re.search(r'\b(?:[A-Z])?(\d{1,4})\b',text,re.I)
        if number:return {'operation':'flight','flight':'SWA'+number[1]}
        identifier=re.search(r'(?i)\bflight\s+([A-Z]{2,3}\s*\d{1,4})\b',text)
        if identifier:return {'operation':'flight','flight':identifier[1]}
    return None


def render(result):
    if 'callsign' not in result:return 'The map view is ready in God’s Eye View in the sidebar. '+result.get('summary','')
    lines=[result['summary']]
    for row in result['positions'].get('rows',[]):
        lines.append(f"{row.get('callsign')}: latitude {row.get('lat')}, longitude {row.get('lon')}; altitude {row.get('altitude_m')} m; ground speed {row.get('speed_mps')} m/s. Last reported: {row.get('last_contact')}.")
    route=(result.get('route') or {}).get('route')
    if route:lines.append('Route metadata: '+airport_label(route.get('origin'))+' → '+airport_label(route.get('destination'))+'. Source: adsbdb; this may describe a usual route, not today’s confirmed itinerary.')
    estimate=result.get('estimate')
    if estimate:lines.append(f"Straight-line distance to the metadata destination (unconfirmed for today’s flight): {estimate['straight_line_km']} km ({estimate['straight_line_miles']} miles). Hypothetical time at current ground speed: {estimate['estimated_minutes']} minutes (rough estimate, not airline ETA).")
    else:lines.append('Remaining distance and time are unavailable without a fresh position and a known destination.')
    track=result.get('track')
    if track:lines.append(f"Recent observed path: {track.get('total',0)} positions. Open the globe to follow the aircraft; use the flight-path details in the sidebar for the returned history.")
    lines.extend(result['limitations'])
    for feed in result['positions'].get('feeds',[]):lines.append('Source: '+str(feed.get('source'))+'; '+str(feed.get('freshness'))+'; observed '+str(feed.get('observed_at'))+'; coverage: '+str(feed.get('coverage'))+'.')
    return '\n'.join(lines)


def airport_label(airport):
    if not airport:return 'unknown airport'
    return str(airport.get('name') or 'unknown airport')+' ('+str(airport.get('code') or '?')+')'


def targeted_flight(callsign, job=None):
    conn=PublicHTTPS('api.adsb.lol',timeout=15)
    if job:
        if job['stop'].is_set():raise ValueError('Request stopped')
        job['connection']=conn
    try:
        conn.request('GET','/v2/callsign/'+normalize_flight(callsign),headers={'User-Agent':'Digi-GodsEyeView/1.0','Accept':'application/json'})
        response=conn.getresponse();raw=response.read(1000001)
        if response.status!=200 or len(raw)>1000000:raise ValueError('Targeted adsb.lol lookup is unavailable')
        payload=json.loads(raw)
        if job and job['stop'].is_set():raise ValueError('Request stopped')
        return normalize_targeted(payload,callsign)
    except (OSError,http.client.HTTPException,KeyError,TypeError) as exc:
        raise ValueError('Targeted adsb.lol lookup did not return usable data') from exc
    finally:
        conn.close()
        if job and job.get('connection') is conn:job['connection']=None


def normalize_targeted(payload,callsign):
    now=payload.get('now')
    if type(now) not in (float,int) or not math.isfinite(now):raise ValueError('Aircraft feed has no valid timestamp')
    now=now/1000 if now>10000000000 else now
    if not -30<=time.time()-now<=120:raise ValueError('Targeted aircraft feed is stale')
    rows=[]
    for ac in payload.get('ac',[]):
        lat,lon=ac.get('lat'),ac.get('lon')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lon)):continue
        if not -90<=lat<=90 or not -180<=lon<=180:continue
        if str(ac.get('flight','')).strip().upper()!=callsign:continue
        if not re.fullmatch('[0-9a-fA-F]{6}',str(ac.get('hex',''))):continue
        age=ac.get('seen_pos',ac.get('seen'))
        if type(age) not in (int,float) or not math.isfinite(age) or not 0<=age<=120:continue
        speed=ac.get('gs');altitude=ac.get('alt_baro');ground=altitude=='ground'
        rows.append({'id':ac['hex'].lower(),'callsign':callsign,'lat':lat,'lon':lon,
                     'last_contact':datetime.datetime.fromtimestamp(now-age,datetime.timezone.utc).isoformat(),
                     'speed_mps':round(speed*.514444,1) if type(speed) in (int,float) and math.isfinite(speed) else None,
                     'altitude_m':round(altitude*.3048) if type(altitude) in (int,float) and math.isfinite(altitude) else None,
                     'on_ground':ground,'course_deg':ac.get('track'),'registration':ac.get('r'),'type_code':ac.get('t')})
    return {'summary':f'{len(rows)} aircraft currently reported for {callsign} by adsb.lol.',
            'data':{'rows':rows,'total':len(rows),'stale_feeds':[],
                    'feeds':[{'source':'adsb.lol targeted callsign lookup','freshness':'current','coverage':'reported matching callsign; receiver coverage varies','observed_at':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat()}]}}
