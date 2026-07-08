from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate("supply@opslens.demo")
print(client.imports())
