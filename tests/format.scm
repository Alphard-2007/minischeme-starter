; 输出格式自查：每行注释是该表达式**期望打印的那一行**。
; 与 tests/format.expected.txt 做逐行比对。
(+ 1 2)                  ; → 3
(- 5)                    ; → -5
(/ 7 2)                  ; → 3
(/ -7 2)                 ; → -3
(/ 2)                    ; → 0.5
(/ 3)                    ; → 0.3333333333333333
(expt 2 -1)              ; → 0.5
(* 1.5 2)                ; → 3.0
#t                       ; → #t
#f                       ; → #f
0                        ; → 0
'x                       ; → x
'()                      ; → ()
'(1 2 3)                 ; → (1 2 3)
(cons 1 2)               ; → (1 . 2)
(cons 1 '())             ; → (1)
'(1 (2 3))               ; → (1 (2 3))
(cons '(1) '(2))         ; → ((1) 2)
''z                      ; → (quote z)
"hello"                  ; → "hello"
"a\nb"                   ; → "a\nb"
"tab\there"              ; → "tab\there"
"quote\"in"              ; → "quote\"in"
"back\\slash"            ; → "back\\slash"
car                      ; → #<procedure>
(define d-fn (lambda (x) x))  ; → d-fn
d-fn                     ; → #<procedure>
(define d-name 1)        ; → d-name
(if #f 'never)
(begin)
(cond ((= 1 2) 'a))
(display "raw")          ; 打印 raw（不换行）
(newline)
(display "no quotes")    ; 打印 no quotes（不带引号）
(newline)
(display '(1 2))         ; 打印 (1 2)
(display #t)
(display 42)
(newline)
(display "a\nb")         ; display 时转义还原成真换行
(newline)
(+ 1 2)
