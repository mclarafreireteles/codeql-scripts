/**
 * @name Change of Literal Encoding
 * @description Encontra literais numericos escritos em uma base diferente da
 *              decimal (hexadecimal ou octal, incluindo a forma legada com
 *              zero a esquerda), que podem levar a interpretacoes equivocadas
 *              do valor real do numero. Baseado na definicao do atomo de
 *              confusao "Change of Literal Encoding" (Torres et al., 2023,
 *              Table 2; Gopstein et al., 2017).
 * @kind table
 * @id js/change-of-literal-encoding
 */

import javascript

from NumberLiteral lit
where
  not lit.getTopLevel().isMinified() and
  (
    lit.getRawValue().regexpMatch("0[xX][0-9a-fA-F]+n?") or // hexadecimal, ex: 0x1A
    lit.getRawValue().regexpMatch("0[oO][0-7]+n?")       or // octal moderno (ES6), ex: 0o31
    lit.getRawValue().regexpMatch("0[0-7]+")                // octal legado, ex: 013
  )
select lit.getFile().getRelativePath(), lit.getLocation().getStartLine(), lit.getLocation().getEndLine(), "Mudança de codificação literal"
