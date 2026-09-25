# Fixture for static-only message argument extraction.
#
# Only arguments that are statically determinable without executing the
# source may be extracted.  Dynamic expressions must be reported as
# non-translatable (None), but they must neither swallow later arguments
# nor calls that follow them in the same file.


# --- Dynamic concatenation must not be partially extracted ----------------

# The literals "a" and "b" surrounding the dynamic name must not be joined
# into a bogus "ab" message.
bad_concat_name = gettext("a" + user + "b")

# A dynamic second segment inside an otherwise static ngettext pair.
bad_plural_concat = ngettext(
    "one thing",
    "many " + things,
    count,
)

# A parenthesized group containing a dynamic name is still dynamic.
bad_paren_dynamic = gettext(("a" + user))

# A percent-formatted message with a literal around the expression.
bad_percent = gettext("Hello " % name)

# A .format() call is dynamic as well.
bad_format = gettext("Hello {name}".format(name=name))

# A truly dynamic f-string (PEP 701 tokenizer on Python 3.12+).
bad_fstring = gettext(f"Hello {name}!")

# Literals adjacent to a dynamic f-string must not be joined either.
bad_fstring_adjacent = gettext("a" f"b{x}" "c")

# An f-string with a constant-looking expression is still dynamic.
bad_fstring_const_expr = gettext(f"Hello {CONST}!")

# Subscripts, lists, dicts and other non-parenthesized groups are dynamic.
bad_subscript = gettext(messages[0])
bad_dict = gettext({"k": "v"})
bad_list = gettext(["a", "b"])

# Keyword argument names make an argument dynamic.
bad_kwarg = gettext("literal", domain="house")


# --- Static concatenation must still be extracted -------------------------

# Adjacent string literals (possibly on multiple lines).
good_adjacent = gettext("foo" "bar")
good_adjacent_multiline = gettext(
    "first "
    "second"
)

# Static concatenation with an explicit + operator.
good_plus = gettext("foo" + "bar")

# Static concatenation grouped in parentheses.
good_paren_group = gettext(("foo" + "bar"))
good_paren_adjacent = gettext(("foo" "bar"))
good_nested_paren_group = gettext((("foo") + ("bar")))

# An f-string without replacement fields is a plain static string.
good_static_fstring = gettext(f"plain f-string")

# Adjacent static f-strings and literals.
good_static_fstring_adjacent = gettext(f"foo" f"bar" "baz")


# --- pgettext/ngettext argument positions per the keywords config ---------

# The dynamic part is in message position 2; the static context survives.
pgettext_dynamic_message = pgettext("context", "a" + user)

# Both plural forms static.
ngettext_static_pair = ngettext("one", "two", count)

# Context and message static despite surrounding parentheses.
pgettext_static_group = pgettext(("ctx"), ("m" + "sg"))

# dpgettext puts the context in position 2.
dpgettext_static = dpgettext("domain", "context", "message")
dpgettext_dynamic = dpgettext("domain", "context", "a" + user)


# --- Nested calls ---------------------------------------------------------

# A non-keyword nested call: no message inside, outer argument is dynamic.
nested_plain_call = gettext(something.method("a", "b"))

# Keyword calls nested as arguments are extracted themselves; this must
# not prevent the call that follows from being extracted.
nested_keyword_calls = add_notice(
    _("nested first"),
    _("nested second"),
)

# A keyword nested after a static first argument: the static message and
# the nested keyword message are both extracted.
nested_first_argument = _("outer", _("deep"))


# --- Multiline translator comments ----------------------------------------

# TRANSLATORS: This is a multiline translator comment whose first line is
# far above the call.  Every line must be preserved and associated with the
# static message below, whose reported line is the one of its first text
# segment.
multiline_comment_message = gettext(
    "commented "
    "message"
)

# TRANSLATORS: a comment immediately followed by a dynamic call must still
# be attached to that call's (None) message position.
commented_dynamic = gettext("a" + user)


# --- A call after all of the above must still be seen ---------------------

final_plain = gettext("final message")
