import urllib.request, json
url = 'https://vmi3020185.contaboserver.net/index.php/s/3kiXJJQC4LiwPrd/download?path=%2F&files=version.json'
resp = urllib.request.urlopen(url, timeout=10)
print(json.loads(resp.read()))