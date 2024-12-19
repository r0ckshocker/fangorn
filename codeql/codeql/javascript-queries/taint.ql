/**
 * @id js/express-endpoints
 * @name Express.js endpoints
 * @description Finds all Express.js endpoints in a JavaScript project.
 * @kind problem
 * @problem.severity error
 * @precision high
 */

 import javascript
 import DataFlow
 import DataFlow::PathGraph
 import semmle.javascript.security.dataflow.ExternalAPIUsedWithUntrustedDataCustomizations
 import semmle.javascript.security.dataflow.ShellCommandInjectionFromEnvironmentCustomizations
 
 class DataflowTest extends TaintTracking::Configuration {
    DataflowTest() { this = "DataflowTest" }
   
     override predicate isSource(Node node) {
       node instanceof ExternalApiUsedWithUntrustedData::Source 
     }
   
     override predicate isSink(Node node) {
       node instanceof ExternalApiUsedWithUntrustedData::Sink 
     }
 }
 
 from DataflowTest cfg, PathNode source, PathNode sink, Express::RouteSetup setup
 where cfg.hasFlowPath(source, sink) and setup.getMethodName() in ["get", "post", "put", "delete"]
 select setup.getMethodName(), setup.getPath(), source, sink

 