import importlib.util
spec=importlib.util.spec_from_file_location('s','c:/Users/WINDOWS/RDC-NCR-Website/backend/rdc_site/settings.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import os
print('DATABASES=', m.DATABASES)
print('ENV POSTGRES_DB=', os.environ.get('POSTGRES_DB'))
print('ENV DATABASE_URL=', os.environ.get('DATABASE_URL'))
