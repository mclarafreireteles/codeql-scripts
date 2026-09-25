/**
 * @name Post-Increment
 * @description Localiza operadores de pos-incremento ou pos-decremento
 *              que estao sendo usados como valores em expressoes maiores.
 * @kind table
 * @id js/post-increment
 */

import javascript

from UpdateExpr u
where
  not u.getTopLevel().isMinified() and
  not u.isPrefix() and
  not u.getParent() instanceof ExprStmt and
  not u.getParent() instanceof ForStmt
select u, "Post Increment"