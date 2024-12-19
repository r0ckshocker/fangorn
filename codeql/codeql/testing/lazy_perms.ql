import javascript

// Find all files with the name "*-routes.ts" in the "apps/main-api/src/routes" directory
from javascript file "apps/main-api/src/routes/**/*-routes.ts"

// Find all calls to the "hasPermission" function
where exists(callExpr) and callExpr.getTarget().getName() = "hasPermission"

// Find all arguments to the "hasPermission" function that are not literals
and exists(argExpr) and not argExpr.getLiteralValue().hasValue()

// Find all arguments to the "hasPermission" function that are not variables
and exists(argExpr) and not argExpr.(Identifier).getTarget()

// Find all arguments to the "hasPermission" function that are not properties of an object
and exists(argExpr) and not argExpr.(MemberAccess).getTarget()

// Find all arguments to the "hasPermission" function that are not function calls
and exists(argExpr) and not argExpr.(CallExpr)

// Find all arguments to the "hasPermission" function that are not array literals
and exists(argExpr) and not argExpr.(ArrayLiteral)

// Find all arguments to the "hasPermission" function that are not object literals
and exists(argExpr) and not argExpr.(ObjectLiteral)

// Find all arguments to the "hasPermission" function that are not template literals
and exists(argExpr) and not argExpr.(TemplateLiteral)

// Find all arguments to the "hasPermission" function that are not arrow functions
and exists(argExpr) and not argExpr.(ArrowFunction)

// Find all arguments to the "hasPermission" function that are not anonymous functions
and exists(argExpr) and not argExpr.(FunctionExpr) and not argExpr.(FunctionDeclaration)

// Find all arguments to the "hasPermission" function that are not class declarations
and exists(argExpr) and not argExpr.(ClassDeclaration)

// Find all arguments to the "hasPermission" function that are not class expressions
and exists(argExpr) and not argExpr.(ClassExpr)

// Find all arguments to the "hasPermission" function that are not object instance specific permissions
and exists(argExpr) and not argExpr.(MemberAccess).getTarget().getName() = "this"

// Find all arguments to the "hasPermission" function that are not high level object permissions
and exists(argExpr) and argExpr.(MemberAccess).getTarget().getName() = "PermissionEnum"

// Return the file path and line number of any calls to "hasPermission" that have both object instance specific permissions and high level object permissions
select callExpr.getFile().getAbsolutePath() + ":" + callExpr.getLocation().getStartLine().toString() + ": " + callExpr.toString()
where exists(argExpr1, argExpr2 |
  argExpr1.(MemberAccess).getTarget().getName() = "this" and
  argExpr2.(MemberAccess).getTarget().getName() = "PermissionEnum"
)
