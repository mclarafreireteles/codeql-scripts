/**
 * @name Assignment as Value
 * @description Identifica o uso do retorno de uma expressao de atribuicao
 *              como valor para outra operacao, o que pode causar confusao 
 *              entre atribuicao e igualdade.
 * @kind table
 * @id js/assignment-as-value
 */

import javascript

from AssignExpr a
where
  not a.getTopLevel().isMinified() and
  not a.getParent() instanceof ExprStmt and
  not a.getParent() instanceof ForStmt
select a.getFile().getRelativePath(), a.getLocation().getStartLine(), a.getLocation().getEndLine(), "Assigment as Value"