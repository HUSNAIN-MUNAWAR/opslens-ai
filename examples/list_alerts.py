from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate()
print(client.alerts())
