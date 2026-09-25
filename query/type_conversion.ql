/**
 * @name Type Conversion
 * @description Detecta operacoes aritmeticas combinando tipos incompativeis
 *              (como Numeros e Strings) que disparam coercao implicita de tipo.
 * @kind table
 * @id js/type-conversion
 */

import javascript

from AddExpr a
where
  not a.getTopLevel().isMinified() and
  (
    (a.getLeftOperand() instanceof NumberLiteral and a.getRightOperand() instanceof StringLiteral) or
    (a.getLeftOperand() instanceof StringLiteral and a.getRightOperand() instanceof NumberLiteral)
  )
select a, "Coerção implícita String/Number"