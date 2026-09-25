/**
 * @name Pre-Increment
 * @description Localiza operadores de pre-incremento ou pre-decremento
 *              sendo avaliados dentro de outras expressoes.
 * @kind table
 * @id js/pre-increment
 */

import javascript

from UpdateExpr u
where
  not u.getTopLevel().isMinified() and
  u.isPrefix() and
  not u.getParent() instanceof ExprStmt and
  not u.getParent() instanceof ForStmt
select u, "Pre-Increment"