import javascript
import DataFlow
import TaintTracking

class MongoConnectFunction extends DataFlow::MethodCallNode {
  MongoConnectFunction() {
    this.getMethodName() = "connect"
  }
}

class MongoCloseFunction extends DataFlow::MethodCallNode {
  MongoCloseFunction() {
    this.getMethodName() = "close" or this.getMethodName() = "disconnect"
  }
}

class ConnectionClosedConfiguration extends TaintTracking::Configuration {
  ConnectionClosedConfiguration() { 
    // Constructor is left empty, no need to assign 'this'
  }

  override predicate isSource(DataFlow::Node node) {
    node instanceof MongoConnectFunction
  }

  override predicate isSink(DataFlow::Node node) {
    exists(MongoCloseFunction close |
      close.getReceiver() = node.getASuccessor()
    )
  }
}

from ConnectionClosedConfiguration cfg, DataFlow::PathNode source, DataFlow::PathNode sink
where cfg.hasFlowPath(source, sink)
select source, sink, source.getNode(), "Flow to possibly unclosed connection"
