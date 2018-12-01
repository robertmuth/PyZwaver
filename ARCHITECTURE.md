# PyZwaver Overview

Note: often additional information can be found in the class comments.


## Driver

All communnication with a Z-Wave stick is handled by the Driver.
The driver understands raw messages at the "transport level" and handles
acks and retries.

Raw messages are handed over to the Driver via SendMessage() and may be queued internally.
Asynchonous messages observed by the Driver are passed along to any Listener registered via
AddListener().


## Commands

Messages pertaining to the applicaiton layer are called commands.

C.f.: [Command Classes](https://www.silabs.com/products/wireless/mesh-networking/z-wave/specification)

Commands are asynchronous. E.g. if you want information about a certain property of a Z-Wave device
in your network you would send a GetXXX command message and hope that the device will send back a 
message with the corresponding ReportXXX command.

##  CommandTranslator

The Command translator simplifies dealing with command messages by translating between
their wire representation and a dicitonary representation.
The translation tries to strike a balance between usability and simplicity, i.e.
it may not interpret every last bit but instead pass pass on data which needs further
decoding. 

The CommandTranslator will register itself as a listener for the Driver.

In turn, other components can register themselves as listeners with the
CommandTranslator.


## Nodeset

A NodeSet represents the collection of all nodes in the network.
The NodeSet will register itself as a listener for the CommandTranslator. 


## Controller

A Controller represents the Z-Wave controller of the network.
It provides APIs for pairing and unpairing nodes but also
helpers for interacting with the  Z-Wave stick, e.g. initializion.
All interactions happen via messages through the Driver.
But unlike command messages, these messages are typically synchronous.


