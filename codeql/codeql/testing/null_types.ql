import javascript

class SequelizeModelField extends PropAccess {
    SequelizeModelField() {
      this.getParent() instanceof ObjectExpr and
      this.getParent().getParent() instanceof CallExpr and
      this.getParent().getParent().(CallExpr).getCalleeName() = "define" and
      this.getInit().(ObjectExpr).("null").getInit().(BooleanLiteral).getBooleanValue() = false
    }
  }
  
  class TypeScriptInterfaceField extends Property {
    TypeScriptInterfaceField() {
      this.getParent() instanceof InterfaceDeclaration and
      this.isOptionalType() instanceof TypeAnnotation and
  }
  
  from TypeScriptInterfaceField tsField, SequelizeModelField seqField
  where tsField.getName() = seqField.getPropertyName()
  select tsField, seqField, "Field " + tsField.getName() + " is optional in the interface but required in the Sequelize model."