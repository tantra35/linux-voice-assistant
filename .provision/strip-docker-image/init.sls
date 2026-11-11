trip-docker-image:
  archive.extracted:
    - name: /opt
    - source: salt://{{ sls.replace('.','/') }}/strip-docker-image-master.tar.gz
    - archive_format: tar
    - enforce_toplevel: False
    - skip_verify: True
    - if_missing: /opt/strip-docker-image-master
