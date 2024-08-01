# Cielim Python Test Connector

The Cielim test connector allows one to send frames and request images from a Cielim instance. One
can create a scene by hand by populating a simulation data frame using the visMessage protobuf schema 
(as defined in vizProtobuffer/vizMessage.proto).

- connect/disconnect to Cielim
- send a spacecraft frame as a protobuf
- request and receive a rendered camera image

From here one can define and incorporate Cielim into a static image generation process (without the need for
Basilisk or a connected scene data generation tool) or define and execute integrated tests.

## Compiling The Protobuf Schema 
For the time being, Cielim (and therefore the Connector) exchange data using the Basilisk ```visMessage.proto```
schema. The python interface corresponding to the schema has been generated from Basilisk and copied into the Cielim 
project. Copying the schema removes the need for Cielim to depend on a second project simply to access the 
compiled version of the schema. The schemas will be kept in synchrony manual for now.  
