/**
 * @id hardcodedPasswords
 * @name passwords
 * @description HARD-CODED PASSWORDS
 * @kind problem
 * @problem.severity recommendation
 */

import javascript

from VariableDeclarator v
where 
  v.getStringValue().toLowerCase().matches("%password%") and
  v.getInit().(StringLiteral).getValue().length() > 0
select v, "This variable may contain a hardcoded password."