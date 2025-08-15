#!/usr/bin/env python
"""Assembler for Xonotic StackVM"""

from pathlib import Path
from argparse import ArgumentParser
from parsy import Parser, regex, seq, string


# Parse cli arguments.
DESCRIPTION = "Xonotic StackVM Assembler"

cli_argument_parser = ArgumentParser(description=DESCRIPTION)

cli_argument_parser.add_argument("file", help="input file")
cli_argument_parser.add_argument("-o", "--output", default="a.cfg", help="output file")

cli_arguments = cli_argument_parser.parse_args()

# Create a parser using parsy.

# FIXME: separate optional and required whitespace.
WHITESPACE = regex(r"\s*")

# TODO: add support for inline and multiline comments.


def token(parser: Parser):
    """
    Creates a parser that parses the input with first parser
    and ignores the whitespace after it.
    """
    return parser << WHITESPACE


def literal(word: str):
    """
    Creates a fixed `word` parser. It mitigates false positives, like
    matching `pop` in `poped`.
    """
    return token(regex(word + r"\b")).desc(word)


# Language grammer: ( [LABEL] [OPCODE [ARG]] )*

# Primitives
IDENTIFIER = regex("[A-Za-z_]+[A-Za-z0-9_]*").desc("ident")
COLON = string(":")
FORWARD_SLASH = string("/")

# Numbers
INTEGER = regex("[0-9]+").desc("integer").map(int)
FLOAT = regex("[0-9]*[.][0-9]+").desc("float").map(float)
NUMBER = FLOAT | INTEGER

# Boolean
TRUE = literal("true").result(1)
FALSE = literal("false").result(0)
BOOLEAN = TRUE | FALSE


# Label
def label(result: str):
    """Maps the result from LABEL parser into a dictionary."""
    return {"type": "label", "value": result}


LABEL = token(IDENTIFIER << COLON).map(label)

# Opcodes

# Stack Operations
# NOTE: There is a special case for 'push' opcode where you can push strings onto
#       the stack. This is achieved by prefixing the string with forward slash ("/").
#       You can also push multi-word strings onto the stack like this: "/hello, world!".
#       But currently single word strings are properly supported by the stackvm. Fasm
#       also only supports single word strings.

PUSH = seq(literal("push"), NUMBER | BOOLEAN | FORWARD_SLASH + IDENTIFIER)
POP = literal("pop")
DUP = literal("dup")
DOT = literal("dot")

STACK_OP = PUSH | POP | DUP | DOT

# Arithemetic Operations
ADD = literal("add")
SUB = literal("sub")
MUL = literal("mul")
DIV = literal("div")
POW = literal("pow")
MIN = literal("min")
MAX = literal("max")

ARITHMETIC_OP = ADD | SUB | MUL | DIV | POW | MIN | MAX

# Branch Operations
JMP = literal("jmp")
JIF = literal("jif")
CALL = literal("call")
RET = literal("ret")

BRANCH_OP = seq(JMP | JIF | CALL, IDENTIFIER) | RET

# Logical Comparision Operations
EQ = literal("eq").result("iseq")
NE = literal("ne").result("isneq")
LT = literal("lt").result("islt")
LE = literal("le").result("isle")
GT = literal("gt").result("isgt")
GE = literal("ge").result("isge")

LOGICAL_OP = EQ | NE | LT | LE | GT | GE

# IO Operations
STORE = literal("store").result("store_l")
LOAD = literal("load").result("load_l")
GSTORE = literal("gstore").result("store_g")
GLOAD = literal("gload").result("load_g")

IO_OP = seq(STORE | LOAD | GSTORE | GLOAD, IDENTIFIER)

# State Operations
HLT = literal("hlt")


# Opcode parser.
def opcode(result):
    """Maps the result from OPCODE parser into a dictionary."""
    if isinstance(result, list):
        # got a opcode with argument.
        return {"type": "opcode", "value": {"opcode": result[0], "arg": result[1]}}
    else:
        return {"type": "opcode", "value": {"opcode": result, "arg": None}}


OPCODE = STACK_OP | ARITHMETIC_OP | BRANCH_OP | LOGICAL_OP | IO_OP | HLT
OPCODE = token(OPCODE).map(opcode)

statement = LABEL | OPCODE

# Main parser.
program = WHITESPACE >> statement.many()

# Assembler backend.
source_path = Path(cli_arguments.file)

if not source_path.exists():
    raise FileNotFoundError(f"'{cli_arguments.file}' no such file or path exists")

# Read the source file
source_file = source_path.open()
source_code = source_file.read()

# Convert source code into ast.
ast = program.parse(source_code)

# Populate the label table, for address lookup for branch instructions.
address_counter = 0
labels = {}

for node in ast:
    node_type = node["type"]

    if node_type == "label":
        label = node["value"]
        label_address = address_counter
        labels[label] = label_address

    elif node_type == "opcode":
        address_counter += 1

    else:
        raise Exception(f"Unknown node of type: {node_type}")

# Reset the address_counter
address_counter = 0

# Generate VM code, don't link it into program memory yet.
instructions = []

for node in ast:
    node_type = node["type"]

    if node_type == "label":
        continue  # don't need label nodes, already processed.

    elif node_type == "opcode":
        opcode = node["value"]["opcode"]
        arg = node["value"]["arg"]

        if arg is not None and opcode in ("call", "jmp", "jif"):
            # Branch instructions, use the label table to substitute
            # the label with it's position in program memory
            label_name = arg

            if label_name not in labels.keys():
                # FIXME: improve error messages by adding error location.
                raise Exception(f"Undefined label: '{label_name}'")

            label_address = labels[label_name]
            instructions.append(f"{opcode} {label_address}")

        elif arg is None:
            instructions.append(f"{opcode}")

        else:
            instructions.append(f"{opcode} {arg}")

    address_counter += 1

# Link the program into program memory. And write to disk.
with open(cli_arguments.output, "w") as output_file:
    vm_program = ""

    for index, instruction in enumerate(instructions):
        vm_program += f'alias __svm.{index} "{instruction}"\n'

    output_file.write(vm_program)
