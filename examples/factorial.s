__main__:
  push 8
  call factorial
  dot
  hlt

factorial:
  store n

  load n
  push 1
  lt
  jif _return_one

  load n
  push 1
  sub
  call factorial
  load n
  mul
  ret

_return_one:
  push 1
  ret
