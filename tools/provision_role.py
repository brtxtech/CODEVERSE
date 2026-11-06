"""Operator-only role assignment for existing Auth users. Never called by the web app."""
import argparse,os,sys,uuid,httpx
p=argparse.ArgumentParser();p.add_argument('--user-id',required=True);p.add_argument('--role',required=True,choices=['visitor','developer','recruiter','security_admin']);a=p.parse_args();uuid.UUID(a.user_id)
url=os.environ['SUPABASE_URL'].rstrip('/');key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
r=httpx.patch(url+'/rest/v1/codeverse_profiles',params={'id':'eq.'+a.user_id},headers={'apikey':key,'Authorization':'Bearer '+key,'Prefer':'return=representation'},json={'role':a.role},timeout=15);r.raise_for_status()
if not r.json():sys.exit('No existing user found. Create an Auth account first.')
print('Role provisioned:',a.role,'for',a.user_id)
