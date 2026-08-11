import os
import sys
import unittest
from contextlib import redirect_stdout
from enum import Enum
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError
from pydantic.v1 import BaseModel as PydanticV1BaseModel

from msup.base import from_dict, from_json, is_pydantic_model, to_dict, to_json, to_kwargs
from msup.cli import CliArg, cli


class Child(BaseModel):
    name: str
    count: int


class PydanticValues(BaseModel):
    required: int
    optional: str | None = None
    values: Annotated[list[int], CliArg(help="values")] = Field(default_factory=lambda: [1, 2])
    mapping: dict[int, list[float]]
    child: Child
    positive: int = Field(gt=0)


class LegacyPydanticValues(PydanticV1BaseModel):
    required: int


class NativePydanticValues(BaseModel):
    value: int = Field(alias="externalValue")


class PydanticState(Enum):
    READY = "ready"
    STOPPED = "stopped"


class PydanticEnumValues(BaseModel):
    state: PydanticState


class CliChild(BaseModel):
    count: int = 1
    label: str = "child"


class CliValues(BaseModel):
    count: Annotated[int, CliArg(help="item count", short="c", env="MSUP_PYDANTIC_COUNT")] = 1
    label: str = "default"
    child: CliChild = Field(default_factory=CliChild)


class DefaultChildValues(BaseModel):
    child: CliChild = CliChild(count=2, label="default")


class FactoryChildValues(BaseModel):
    child: CliChild = Field(default_factory=lambda: CliChild(count=3, label="factory"))


class RequiredChildValues(BaseModel):
    child: CliChild


pydantic_received = []


def cli_values_command(args: CliValues):
    pydantic_received.append(args)


def default_child_command(args: DefaultChildValues):
    pydantic_received.append(args)


def factory_child_command(args: FactoryChildValues):
    pydantic_received.append(args)


def required_child_command(args: RequiredChildValues):
    pydantic_received.append(args)


class PydanticSerializationTests(unittest.TestCase):
    def test_public_pydantic_detector_accepts_classes_and_instances(self):
        self.assertTrue(is_pydantic_model(PydanticValues))
        self.assertTrue(
            is_pydantic_model(PydanticValues(required=1, mapping={}, child=Child(name="child", count=1), positive=1))
        )
        self.assertFalse(is_pydantic_model(object))
        with self.assertRaisesRegex(TypeError, "Pydantic v1 models are not supported"):
            is_pydantic_model(LegacyPydanticValues)

    def test_public_helpers_delegate_to_pydantic_native_conversion(self):
        value = from_dict(NativePydanticValues, {"externalValue": "3"})
        self.assertEqual(value, NativePydanticValues(externalValue=3))
        self.assertEqual(to_dict(value), {"value": 3})

    def test_enum_values_use_the_shared_serialization_path(self):
        value = PydanticEnumValues(state=PydanticState.READY)
        self.assertEqual(to_dict(value), {"state": "ready"})
        self.assertEqual(from_json(PydanticEnumValues, s=to_json(value, indent=None)), value)

    def test_public_helpers_round_trip_scalar_collections_and_nested_models(self):
        value = from_dict(
            PydanticValues,
            {
                "required": "3",
                "optional": "label",
                "values": ["4", 5],
                "mapping": {"6": ["1.5", 2]},
                "child": {"name": "nested", "count": "7"},
                "positive": 8,
            },
        )
        expected = PydanticValues(
            required=3,
            optional="label",
            values=[4, 5],
            mapping={6: [1.5, 2.0]},
            child=Child(name="nested", count=7),
            positive=8,
        )

        self.assertEqual(value, expected)
        self.assertEqual(
            to_dict(value),
            {
                "required": 3,
                "optional": "label",
                "values": [4, 5],
                "mapping": {6: [1.5, 2.0]},
                "child": {"name": "nested", "count": 7},
                "positive": 8,
            },
        )
        self.assertEqual(from_dict(PydanticValues, to_dict(value)), value)
        kwargs = to_kwargs(PydanticValues, value)
        self.assertEqual(kwargs["child"], value.child)
        self.assertEqual(kwargs["values"], value.values)

        serialized = to_json(value, indent=None)
        self.assertEqual(from_json(PydanticValues, s=serialized), value)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            to_json(value, file_like=str(path), indent=None)
            self.assertEqual(from_json(PydanticValues, path=str(path)), value)

    def test_omitted_values_use_pydantic_defaults_and_default_factories(self):
        value = from_dict(
            PydanticValues,
            {
                "required": 3,
                "mapping": {},
                "child": {"name": "nested", "count": 7},
                "positive": 1,
            },
        )

        self.assertIsNone(value.optional)
        self.assertEqual(value.values, [1, 2])
        self.assertIsNot(
            value.values,
            PydanticValues(
                required=3,
                mapping={},
                child=Child(name="nested", count=7),
                positive=1,
            ).values,
        )

    def test_nested_models_accept_instances_and_dicts(self):
        common = {
            "required": 3,
            "mapping": {},
            "positive": 1,
        }
        expected_child = Child(name="nested", count=7)
        inputs = [
            expected_child,
            {"name": "nested", "count": "7"},
        ]
        for child in inputs:
            with self.subTest(child=child):
                self.assertEqual(
                    from_dict(PydanticValues, {**common, "child": child}).child,
                    expected_child,
                )

    def test_pydantic_validation_errors_are_preserved(self):
        with self.assertRaises(ValidationError):
            from_dict(
                PydanticValues,
                {
                    "required": 3,
                    "mapping": {},
                    "child": {"name": "nested", "count": 7},
                    "positive": 0,
                },
            )

    def test_pydantic_v1_models_are_rejected_explicitly(self):
        with self.assertRaisesRegex(TypeError, "Pydantic v1 models are not supported"):
            from_dict(LegacyPydanticValues, {"required": 3})


class PydanticCliTests(unittest.TestCase):
    def setUp(self):
        self.old_argv = sys.argv
        self.old_count = os.environ.pop("MSUP_PYDANTIC_COUNT", None)
        pydantic_received.clear()

    def tearDown(self):
        sys.argv = self.old_argv
        if self.old_count is None:
            os.environ.pop("MSUP_PYDANTIC_COUNT", None)
        else:
            os.environ["MSUP_PYDANTIC_COUNT"] = self.old_count
        pydantic_received.clear()

    def invoke(self, command, argv):
        sys.argv = ["program", *argv]
        cli(command)
        return pydantic_received.pop()

    def test_scalar_default_option_and_annotated_help_text(self):
        self.assertEqual(self.invoke(cli_values_command, []), CliValues())
        self.assertEqual(
            self.invoke(cli_values_command, ["-c", "4", "--label", "updated"]),
            CliValues(count=4, label="updated"),
        )

        sys.argv = ["program", "--help"]
        output = StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(output):
            cli(cli_values_command)
        self.assertIn("-c", output.getvalue())
        self.assertIn("item count. Default: 1", output.getvalue())

    def test_cli_environment_config_and_default_precedence(self):
        self.assertEqual(
            self.invoke(cli_values_command, ["--Args", '{"count": 2, "label": "config"}']),
            CliValues(count=2, label="config"),
        )

        os.environ["MSUP_PYDANTIC_COUNT"] = "3"
        self.assertEqual(
            self.invoke(cli_values_command, ["--Args", '{"count": 2, "label": "config"}']),
            CliValues(count=3, label="config"),
        )
        self.assertEqual(
            self.invoke(
                cli_values_command,
                ["--Args", '{"count": 2, "label": "config"}', "--count", "4"],
            ),
            CliValues(count=4, label="config"),
        )

    def test_nested_json_configuration_and_dotted_override(self):
        self.assertEqual(
            self.invoke(
                cli_values_command,
                ["--child", '{"count": 2, "label": "json"}', "--child.count", "3"],
            ),
            CliValues(child=CliChild(count=3, label="json")),
        )
        self.assertEqual(
            self.invoke(
                cli_values_command,
                ["--Args", '{"child": {"count": 4, "label": "config"}}', "--child.label", "override"],
            ),
            CliValues(child=CliChild(count=4, label="override")),
        )

    def test_omitted_nested_default_and_factory_are_left_to_pydantic(self):
        self.assertEqual(
            self.invoke(default_child_command, []),
            DefaultChildValues(child=CliChild(count=2, label="default")),
        )
        self.assertEqual(
            self.invoke(factory_child_command, []),
            FactoryChildValues(child=CliChild(count=3, label="factory")),
        )

    def test_omitted_required_nested_model_raises_pydantic_error(self):
        with self.assertRaises(ValidationError):
            self.invoke(required_child_command, [])


if __name__ == "__main__":
    unittest.main()
