import datetime
import unittest
from unittest.mock import patch
from digi.gods_eye import GodsEye, normalize_flight, remaining_estimate, request, normalize_targeted

class GodsEyeTests(unittest.TestCase):
    def test_airline_callsigns(self):
        for value in ('WN2456','Southwest 2456','Southwest Airlines 2456','SWA2456'):
            self.assertEqual(normalize_flight(value),'SWA2456')
        with self.assertRaises(ValueError):normalize_flight('A2456')
        self.assertEqual(request('hey digi, Where is flight A2456 south west')['flight'],'SWA2456')
        self.assertEqual(request('Show me flight WN2456')['flight'],'SWA2456')
        self.assertEqual(request('Show me SWA2456')['flight'],'SWA2456')
    def test_places_and_non_map_requests(self):
        self.assertIn('Paris France',request('hey digi, show me parris frans')['arguments_json'])
        for text in ('show me my screen','show me how to install this','implement show me Paris','translate show me Paris','Show research model status'):
            self.assertIsNone(request(text))
    def test_estimate_requires_fresh_evidence(self):
        now=datetime.datetime.now(datetime.timezone.utc)
        row={'lat':0,'lon':0,'last_contact':now.isoformat(),'speed_mps':200,'on_ground':False}
        dest={'lat':0,'lon':1}
        estimate=remaining_estimate(row,dest,{'feeds':[{'freshness':'fresh'}]})
        self.assertAlmostEqual(estimate['straight_line_km'],111.2,places=1)
        self.assertAlmostEqual(estimate['estimated_minutes'],9.3,places=1)
        self.assertIsNone(remaining_estimate(row,dest,{'feeds':[{'freshness':'stale'}]}))
        row['last_contact']=(now-datetime.timedelta(minutes=5)).isoformat()
        self.assertIsNone(remaining_estimate(row,dest,{}))
    def test_mcp_result_and_selected_view(self):
        api=GodsEye()
        def rpc(method,params=None,job=None):
            if method=='tools/list':return {'tools':[{'name':'show_in_gods_eye_view'},{'name':'panel_request'}]}
            return {'content':[{'type':'text','text':'Paris selected.'},{'type':'text','text':'{"view":{"camera":{"lat":48.8,"lon":2.3}}}'}],'structuredContent':{'view':{'camera':{'lat':48.8,'lon':2.3}}}}
        with patch.object(api,'rpc',side_effect=rpc):
            result=api.query('show_in_gods_eye_view',{})
            self.assertEqual(result['summary'],'Paris selected.')
            self.assertEqual(api.state()['revision'],1)
            with self.assertRaises(ValueError):api.query('panel_request',{})
    def test_missing_aircraft_never_produces_eta(self):
        api=GodsEye()
        with patch.object(api,'query',return_value={'summary':'Not reported.','data':{'rows':[]}}),patch('digi.gods_eye.targeted_flight',return_value={'data':{'rows':[]}}):
            result=api.flight('WN2456')
            self.assertIsNone(result['estimate'])
            self.assertIsNone(result['track'])
            self.assertTrue(result['limitations'])

    def test_targeted_lookup_rejects_stale_positions_and_wrong_callsigns(self):
        import time
        now=time.time()
        ac={'hex':'abc123','flight':'SWA2456 ','lat':32,'lon':-100,'seen_pos':1,'gs':200,'alt_baro':10000}
        result=normalize_targeted({'now':now*1000,'ac':[ac]},'SWA2456')
        self.assertEqual(result['data']['rows'][0]['altitude_m'],3048)
        self.assertEqual(result['data']['rows'][0]['speed_mps'],102.9)
        self.assertEqual(normalize_targeted({'now':now*1000,'ac':[ac]},'SWA1')['data']['rows'],[])
        with self.assertRaises(ValueError):normalize_targeted({'now':(now-300)*1000,'ac':[ac]},'SWA2456')
        ac['seen_pos']=300
        self.assertEqual(normalize_targeted({'now':now*1000,'ac':[ac]},'SWA2456')['data']['rows'],[])

    def test_observed_camera_is_bounded(self):
        api=GodsEye()
        camera={'lat':48.8,'lon':2.3,'altitude_m':19000,'heading_deg':0,'pitch_deg':-90}
        api.observe(camera)
        self.assertEqual(api.state()['observed_view']['camera']['lat'],48.8)
        camera['lat']=100
        with self.assertRaises(ValueError):api.observe(camera)

    def test_conflicting_departure_suppresses_arrival_estimate(self):
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        api=GodsEye()
        row={'id':'abc123','lat':30,'lon':-95,'last_contact':now,'speed_mps':200}
        view={'camera':{'lat':30,'lon':-95,'altitude_m':50000},'layers':['flights'],'follow':{'kind':'aircraft','id':'abc123'}}
        def query(name,args,job=None):
            if name=='find_aircraft':return {'summary':'Found.','data':{'rows':[row],'view':view,'feeds':[{'freshness':'current'}]}}
            if name=='get_aircraft_info':return {'data':{'route':{'origin':{'lat':37,'lon':-122},'destination':{'lat':36,'lon':-115}}}}
            if name=='get_aircraft_track':return {'data':{'points':[{'lat':30,'lon':-95,'altitude_m':300},{'lat':31,'lon':-95,'altitude_m':800}]}}
            return {'data':{}}
        with patch.object(api,'query',side_effect=query):
            result=api.flight('SWA1675')
        self.assertIsNone(result['estimate'])
        self.assertTrue(any('conflicts' in s for s in result['limitations']))

if __name__=='__main__':unittest.main()
