import javascript

from File f
select f.getExtension(), count(f) as quantidade
order by quantidade desc