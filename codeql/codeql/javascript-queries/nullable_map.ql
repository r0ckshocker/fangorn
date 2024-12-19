import javascript

from DataFlow::MethodCallNode mapCall, DataFlow::ValueNode base
where
  mapCall.getMethodName() = "map" and
  base = mapCall.getReceiver() and
  not exists(IfStmt ifStmt | ifStmt.getCondition() = base.asExpr())
select mapCall, "The array " + base + " might be nullable. Consider using ?.map instead of .map."