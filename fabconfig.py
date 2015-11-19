config = {
    'port': '8030',
    'app_dir': 'casepro',
    'friendly_name': 'CasePro',
    'repository': 'ssh://git@github.com/rapidpro/casepro.git',
    'domain': 'upartners.org',
    'name': 'casepro',
    'repo': 'casepro',
    'user': 'casepro',
    'env': 'env',
    'settings': 'settings.py.dev',
    'dbms': 'psql',
    'db': 'casepro',
    'custom_domains': 'upartners.org *.upartners.org partners.ureport.in *.partners.ureport.in upartners.staging.nyaruka.com *.upartners.staging.nyaruka.com',
    'prod_host': 'partner1',
    'sqldump': False,
    'celery': True,
    'processes': ('celery',),
    'compress': True,
    'elb': {
        'name': 'UPartners',
        'region': 'eu-west-1',
        'primary': 'partner1',
        'instances': [
            {'name': 'partner1', 'host': 'partner1.upartners.org', 'id': 'i-5ccaec1f'},
            {'name': 'partner2', 'host': 'partner2.upartners.org', 'id': 'i-e89fd8aa'}
        ]
    }
}
