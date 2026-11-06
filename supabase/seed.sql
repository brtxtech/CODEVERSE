-- DEV ONLY sample data (runs on `supabase db reset`, never on production).
-- Replace with the full contents of your geo.py / companies.json / repos.json.

insert into public.geo_places (city, country, region, area) values
 ('bilbao','ES','Europe','Basque Country'), ('san sebastián','ES','Europe','Basque Country'),
 ('donostia','ES','Europe','Basque Country'), ('vitoria','ES','Europe','Basque Country'),
 ('madrid','ES','Europe','Community of Madrid'), ('barcelona','ES','Europe','Catalonia'),
 ('valencia','ES','Europe','Valencian Community'), ('sevilla','ES','Europe','Andalusia'),
 ('málaga','ES','Europe','Andalusia'), ('zaragoza','ES','Europe','Aragon')
on conflict do nothing;

insert into public.companies (name, focus) values
 ('BBVA','{software,data,ai}'), ('Accenture','{consulting,software}'), ('Capgemini','{consulting,software}'),
 ('Telefónica','{telecom,software}'), ('Ibermática','{consulting,software}'), ('Tecnalia','{research,ai}'),
 ('NTT DATA','{consulting,software}'), ('Vicomtech','{ai,research}'), ('Indra / Minsait','{consulting,enterprise}'),
 ('Amadeus','{software}')
on conflict do nothing;

insert into public.company_offices (company_id, city, country, area, region, is_hq)
select c.id, o.city, o.country, o.area, 'Europe', o.is_hq
from (values
 ('BBVA','bilbao','ES','Basque Country',true), ('Accenture','bilbao','ES','Basque Country',false),
 ('Capgemini','bilbao','ES','Basque Country',false), ('Telefónica','bilbao','ES','Basque Country',false),
 ('Ibermática','bilbao','ES','Basque Country',true), ('Tecnalia','bilbao','ES','Basque Country',true),
 ('NTT DATA','bilbao','ES','Basque Country',false), ('Vicomtech','san sebastián','ES','Basque Country',true),
 ('Indra / Minsait','bilbao','ES','Basque Country',false), ('Amadeus','madrid','ES','Community of Madrid',true)
) as o(name, city, country, area, is_hq)
join public.companies c on c.name = o.name
on conflict do nothing;

insert into public.repos (full_name, description, language, topics, stars, license, pushed_at, good_first_issues) values
 ('bregman-arie/devops-exercises','DevOps exercises and questions','Python','{python,linux,git,sql,docker,devops}',70000,'MIT',now()-interval '20 days',5),
 ('Gallopsled/pwntools','CTF framework and exploit development library','Python','{python,ctf,linux,cybersecurity}',12000,'MIT',now()-interval '30 days',3)
on conflict (full_name) do nothing;
