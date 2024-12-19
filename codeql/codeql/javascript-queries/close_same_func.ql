import javascript

from Function f
where 
  exists(CallExpr connect | 
    connect.getCalleeName() = "connect" and 
    connect.getEnclosingFunction() = f and
    not exists(CallExpr close | 
      (close.getCalleeName() = "close" or close.getCalleeName() = "disconnect") and
      close.getEnclosingFunction() = f
    )
  )
select f, f.getName(), f.getFile().getRelativePath(), "This function opens a MongoDB connection but may not close it."
