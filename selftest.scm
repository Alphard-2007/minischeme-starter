; 自查程序：覆盖 spec 各条特性，尤其是 §11 排错表列出的陷阱。
; 每行注释是期望输出。

; --- §5 算术：可变参数、负数截断、单参数倒数 ---
(+ 1 2 3)                ; → 6
(+)                      ; → 0
(- 10 4 1)               ; → 5
(- 5)                    ; → -5
(- 5)                    ; → -5
(* 2 3 4)                ; → 24
(*)                      ; → 1
(/ 7 2)                  ; → 3
(/ -7 2)                 ; → -3
(/ 7 -2)                 ; → -3
(/ -7 -2)                ; → 3
(/ 2)                    ; → 0.5
(/ 100 5 2)              ; → 10
(modulo 17 5)            ; → 2
(modulo -17 5)           ; → 3
(quotient 17 5)          ; → 3
(quotient -7 2)          ; → -3
(expt 2 10)              ; → 1024
(expt 3 0)               ; → 1
(abs (- 5 9))            ; → 4
(abs -3)                 ; → 3

; --- §5 比较：链式、单项、数字与符号 ---
(= 1 1)                  ; → #t
(= 1 1.0)                ; → #t
(< 2 3 4)                ; → #t
(< 2 3 3)                ; → #f
(> 5 5)                  ; → #f
(<= 1 1 2)               ; → #t
(>= 3 3 2)               ; → #t
(< 5)                    ; → #t
(= 'a 'a)                ; → #t
(= 'a 'b)                ; → #f
(< 'a 'b)                ; → #t
(= "x" "x")              ; → #t
(= #t #t)                ; → #t
(= #t 1)                 ; → #f

; --- §4.4 短路：只有 #f 是假，0 和 () 都是真 ---
(and #f (/ 1 0))         ; → #f
(or #t (/ 1 0))          ; → #t
(and)                    ; → #t
(or)                     ; → #f
(and 1 2 3)              ; → 3
(or #f #f 7)             ; → 7
(or #f #f)               ; → #f
(and #t #t)              ; → #t
(if 0 'truthy 'falsy)    ; → truthy
(if '() 'truthy 'falsy)  ; → truthy
(if "" 'truthy 'falsy)   ; → truthy
(not 0)                  ; → #f
(not '())                ; → #f
(not #f)                 ; → #t
(not 5)                  ; → #f

; --- §4.1 quote ---
'x                       ; → x
'(1 2 3)                 ; → (1 2 3)
'()                      ; → ()
(quote y)                ; → y
''z                      ; → (quote z)
'(a . b)                 ; → (a . b)
'(1 (2 3) 4)             ; → (1 (2 3) 4)

; --- §4.2 if：省略假分支时不打印 ---
(if (> 3 2) 'yes 'no)    ; → yes
(if #f 'bad 'good)       ; → good
(if (null? '()) 1 2)     ; → 1
(if #f 'never)
(display "after-if")     ; 打印 after-if（上一行没有输出）
(newline)

; --- §4.3 cond ---
(cond ((= 1 2) 'a) ((= 2 2) 'b) (else 'c))  ; → b
(cond (else 'd))                            ; → d
(cond ((> 2 3)) (else 42))                  ; → 42
(cond ((= 1 2) 'a))                         ; （全不匹配，不打印）
(cond (#f 'a) (5 'e))                       ; → e
(cond ((and #t #t) (begin 1 2)))            ; → 2
(display "after-cond")(newline)

; --- §4.5 define：结果是符号名；函数简写；递归可见自身 ---
(define pi 3)            ; → pi
(+ pi 1)                 ; → 4
(define (square x) (* x x))  ; → square
(square 7)               ; → 49
(define redefined 1)     ; → redefined
(define redefined 2)     ; → redefined
redefined                ; → 2

; --- §4.6 lambda ---
(define sq2 (lambda (x) (* x x)))  ; → sq2
((lambda (x) (* x 2)) 5)           ; → 10
(procedure? (lambda (x) x))        ; → #t

; --- §9 词法作用域 + 闭包 ---
(define (make-adder n) (lambda (x) (+ x n)))  ; → make-adder
(define add5 (make-adder 5))                  ; → add5
(add5 10)                                     ; → 15
((make-adder 100) 7)                          ; → 107
(define (counter) (let ((n 0)) (lambda () n)))  ; → counter
((counter))                                   ; → 0
(define x-global 10)                          ; → x-global
(define (shadow-x x) (+ x x-global))          ; → shadow-x
(shadow-x 1)                                  ; → 11

; --- §4.7 let：并行绑定（后一个绑定看不见前一个）---
(let ((x 3) (y 4)) (+ x y))                   ; → 7
(let ((a 1)) (let ((b (+ a 1))) (* a b)))     ; → 2
(let ((a 1)) (let ((a 5) (b a)) (list a b)))   ; → (5 1)  ← 并行绑定：b 取的是外层的 a=1

; --- §4.8 begin ---
(begin (define z 1) (+ z 41))                 ; → 42
(begin 1 2 3)                                 ; → 3
(begin)
(display "after-begin")(newline)

; --- §6 列表与点对 ---
(car '(1 2 3))               ; → 1
(cdr '(1 2 3))               ; → (2 3)
(cons 1 '(2 3))              ; → (1 2 3)
(cons 1 2)                   ; → (1 . 2)
(cons '(1) '(2))             ; → ((1) 2)
(list 1 2 3)                 ; → (1 2 3)
(list)                       ; → ()
(length '(a b c d))          ; → 4
(length '())                 ; → 0
(append '(1 2) '(3 4))       ; → (1 2 3 4)
(append '() '(1))            ; → (1)
(append '(1) '() '(2))       ; → (1 2)
(null? '())                  ; → #t
(null? '(1))                 ; → #f
(pair? '(1 2))               ; → #t
(pair? '())                  ; → #f
(list? '(1 2))               ; → #t
(list? (cons 1 2))           ; → #f
(list? '())                  ; → #t

; --- §5 eq? / equal?（§11 的三个陷阱）---
(eq? '() '())                ; → #t
(eq? '(1) '(1))              ; → #f
(eq? 'a 'a)                  ; → #t
(eq? 1 1)                    ; → #t
(eq? #t #t)                  ; → #t
(eq? #t 1)                   ; → #f
(equal? '(1 2 3) (list 1 2 3))  ; → #t
(equal? 'a "a")              ; → #f
(equal? #t 1)                ; → #f
(equal? '(1 (2)) '(1 (2)))   ; → #t
(equal? 1 1.0)               ; → #t
(equal? "s" "s")             ; → #t
(equal? '() '())             ; → #t

; --- §5 谓词 ---
(number? 5)                  ; → #t
(number? 'x)                 ; → #f
(number? #t)                 ; → #f
(boolean? #t)                ; → #t
(boolean? 0)                 ; → #f
(symbol? 'x)                 ; → #t
(symbol? "x")                ; → #f
(string? "s")                ; → #t
(string? 's)                 ; → #f
(procedure? car)             ; → #t
(procedure? 1)               ; → #f
(procedure? square)          ; → #t
(zero? 0)                    ; → #t
(zero? 1)                    ; → #f
(even? 8)                    ; → #t
(even? 7)                    ; → #f
(odd? 7)                     ; → #t
(odd? 8)                     ; → #f

; --- §5 输出：display 字符串不带引号 ---
(display "a")                ; 打印 a
(display 1)                  ; 打印 1
(display '(1 2))             ; 打印 (1 2)
(display #t)                 ; 打印 #t
(newline)
"tab\there"                  ; → "tab\there"
"quote\"in"                  ; → "quote\"in"
"back\\slash"                ; → "back\\slash"

; --- §7 递归：在列表上递归定义 map / filter ---
(define (my-map f xs) (if (null? xs) '() (cons (f (car xs)) (my-map f (cdr xs)))))  ; → my-map
(my-map (lambda (x) (* x x)) '(1 2 3 4))  ; → (1 4 9 16)
(define (my-filter p xs)
  (cond ((null? xs) '())
        ((p (car xs)) (cons (car xs) (my-filter p (cdr xs))))
        (else (my-filter p (cdr xs)))))   ; → my-filter
(my-filter even? '(1 2 3 4 5 6))          ; → (2 4 6)
(define (deep n) (if (= n 0) 0 (deep (- n 1))))  ; → deep
(deep 5000)                               ; → 0
