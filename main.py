import json
import math
import textwrap
from dataclasses import dataclass, asdict
from typing import TypedDict, Any
from collections.abc import Callable, Iterable
from pathlib import Path

DEFAULT_CONTACT_FILE = "contacts.json"
CONTACTS_PER_PAGE = 10
YES_ANSWERS = {"1", "y", "yes", "д", "да", "true", "t"}
NO_ANSWERS = {"0", "n", "no", "н", "нет", "false", "f"}
TABLE_PADDING = 2
TABLE_COLUMN_MAX_WIDTH = 32
BOLD_START = "\033[1m"
BOLD_RESET = "\033[0m"


class AppError(Exception):
    pass


class MenuAction(TypedDict):
    title: str
    action: Callable[[], bool]


@dataclass
class Contact:
    id: int
    name: str
    phone: str
    comment: str = ""

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id <= 0:
            raise AppError("ID контакта должен быть положительным числом")
        if not isinstance(self.name, str) or not self.name.strip():
            raise AppError("Имя контакта должно быть непустой строкой")
        if not isinstance(self.phone, str) or not self.phone.strip():
            raise AppError("Телефон контакта должен быть непустой строкой")
        if not isinstance(self.comment, str):
            raise AppError("Комментарий должен быть строкой")

    def set_name(self, name: str) -> None:
        if not name.strip():
            raise AppError("Имя контакта должно быть непустой строкой")
        self.name = name

    def set_phone(self, phone: str) -> None:
        if not phone.strip():
            raise AppError("Телефон контакта должен быть непустой строкой")
        self.phone = phone

    def set_comment(self, comment: str) -> None:
        self.comment = comment

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def copy(self) -> "Contact":
        return Contact(
            id=self.id,
            name=self.name,
            phone=self.phone,
            comment=self.comment,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "Contact":
        if not isinstance(data, dict):
            raise AppError("Контакт должен быть объектом JSON")

        required_fields = ("name", "phone", "id")
        for field in required_fields:
            if field not in data:
                raise AppError(f"В контакте отсутствует поле: {field}")

        return cls(
            id=data["id"],
            name=data["name"],
            phone=data["phone"],
            comment=data.get("comment", ""),
        )


class AppState(TypedDict):
    contacts: list[Contact]
    contacts_path: Path
    contacts_id_idx: dict[int, int]
    has_changes: bool
    next_contact_id: int


def print_blank_line() -> None:
    print()


def print_title(title: str) -> None:
    border = "=" * (len(title) + 4)
    print_blank_line()
    print(border)
    print(f"  {title}")
    print(border)


def print_section(title: str) -> None:
    print_blank_line()
    print(title)
    print("-" * len(title))


def print_success(message: str) -> None:
    print(f"[OK] {message}")


def print_warning(message: str) -> None:
    print(f"[!] {message}")


def print_error(message: str) -> None:
    print(f"[Ошибка] {message}")


def print_info(message: str) -> None:
    print(f"[i] {message}")


def format_cell(value: Any, width: int) -> str:
    text = str(value)
    return f" {text:<{width}} "


def format_bold_cell(value: Any, width: int) -> str:
    text = str(value)
    return f" {BOLD_START}{text:<{width}}{BOLD_RESET} "


def wrap_cell(value: Any, width: int) -> list[str]:
    text = str(value)
    lines = textwrap.wrap(
        text,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    )

    return lines or [""]


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    columns_width = [len(header) for header in headers]

    for row in rows:
        for index, value in enumerate(row):
            columns_width[index] = max(columns_width[index], len(str(value)))

    columns_width = [
        min(width, max(TABLE_COLUMN_MAX_WIDTH, len(headers[index])))
        for index, width in enumerate(columns_width)
    ]

    separator = "+".join("-" * (width + TABLE_PADDING) for width in columns_width)
    border = f"+{separator}+"

    print(border)
    print(
        "|"
        + "|".join(
            format_bold_cell(header, columns_width[index])
            for index, header in enumerate(headers)
        )
        + "|"
    )
    print(border)

    for row in rows:
        wrapped_cells = [
            wrap_cell(value, columns_width[index])
            for index, value in enumerate(row)
        ]
        row_height = max(len(cell) for cell in wrapped_cells)

        for line_index in range(row_height):
            print(
                "|"
                + "|".join(
                    format_cell(
                        cell[line_index] if line_index < len(cell) else "",
                        columns_width[index],
                    )
                    for index, cell in enumerate(wrapped_cells)
                )
                + "|"
            )
        print(border)


def contact_to_row(contact: Contact) -> list[Any]:
    return [
        contact.id,
        contact.name,
        contact.phone,
        contact.comment,
    ]


def load_contacts() -> tuple[list[Contact], Path]:
    path_str = input(
        f"Файл контактов [{DEFAULT_CONTACT_FILE}]: "
    ).strip()

    path = Path(path_str) if path_str else Path(DEFAULT_CONTACT_FILE)

    if path.is_dir() or not path.suffix:
        path = path / DEFAULT_CONTACT_FILE

    if path.suffix != ".json":
        raise AppError("Файл с контактами должен иметь расширение .json")

    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise AppError(f"Ошибка при создании файла: {path}")

        try:
            with path.open("w", encoding="utf-8") as file:
                json.dump([], file)
        except OSError:
            raise AppError(f"Ошибка при создании файла: {path}")

        return [], path

    try:
        with path.open("r", encoding="utf-8") as file:
            contacts = json.load(file)
    except OSError:
        raise AppError(f"Ошибка при чтении файла: {path}")
    except json.JSONDecodeError:
        raise AppError(f"Ошибка декодирования JSON файла: {path}")

    if not isinstance(contacts, list):
        raise AppError(f"Некорректный формат файла контактов: {path}")

    contacts = [Contact.from_dict(contact) for contact in contacts]

    return contacts, path


def save_contacts(state: AppState) -> bool:
    contacts_path = state["contacts_path"]
    temp_contacts_path = contacts_path.with_suffix(f"{contacts_path.suffix}.tmp")
    contacts = [contact.to_dict() for contact in state["contacts"]]

    try:
        with temp_contacts_path.open("w", encoding="utf-8") as file:
            json.dump(contacts, file, ensure_ascii=False, indent=2)
        temp_contacts_path.replace(contacts_path)
    except OSError:
        raise AppError(f"Ошибка при сохранении файла: {contacts_path}")

    state["has_changes"] = False
    print_success(f"Контакты сохранены в файл: {contacts_path}")
    return True


def print_contact(contact: Contact) -> None:
    print_table(
        ["ID", "Имя", "Телефон", "Комментарий"],
        [contact_to_row(contact)],
    )


def print_contacts(contacts: Iterable[Contact]) -> None:
    rows = [contact_to_row(contact) for contact in contacts]
    if not rows:
        print_info("Список контактов пуст")
        return

    print_table(["ID", "Имя", "Телефон", "Комментарий"], rows)


def input_yes_no(question: str) -> bool:
    while True:
        answer = input(f"{question} (да/нет): ")
        answer = answer.strip().lower()

        if answer in YES_ANSWERS:
            return True

        if answer in NO_ANSWERS:
            return False

        print_error("Введите да или нет")


def show_contacts_pagination(state: AppState, contacts: list[Contact], page_size: int) -> bool:
    if page_size <= 0:
        raise AppError(
            "Количество контактов на страницу не может быть меньше 1"
        )

    def next_page() -> bool:
        nonlocal current_page

        if current_page == pages_count:
            return True

        current_page += 1
        return True

    def previous_page() -> bool:
        nonlocal current_page

        if current_page == 1:
            return True

        current_page -= 1
        return True

    def select_page() -> bool:
        nonlocal current_page

        page_input = input(f"Введите номер страницы [1-{pages_count}]: ").strip()
        if not page_input.isdigit():
            print_error("Необходимо ввести номер страницы")
            return True

        selected_page = int(page_input)
        if selected_page not in range(1, pages_count + 1):
            print_error("Такой страницы не существует")
            return True

        current_page = selected_page
        return True

    current_page = 1

    while True:
        print_title("Список контактов")

        contacts_count = len(contacts)

        if not contacts_count:
            print_info("Список контактов пуст")
            break

        pages_count = max(1, int(math.ceil(contacts_count / page_size)))
        current_page = min(current_page, pages_count)

        page_start = (current_page - 1) * page_size
        page_end = page_start + page_size
        contacts_on_page = contacts[page_start:page_end]

        print_contacts(contacts_on_page)
        print_info(f"Всего контактов: {contacts_count}")
        print_info(f"Страница {current_page} из {pages_count}")

        if not process_actions([
            {
                "title": "Следующая страница",
                "action": next_page,
            },
            {
                "title": "Предыдущая страница",
                "action": previous_page,
            },
            {
                "title": "Выбор страницы",
                "action": select_page,
            },
            {
                "title": "Выбор контакта",
                "action": lambda: select_contact(state, contacts_on_page),
            },
            {
                "title": "Назад",
                "action": lambda: False
            },
        ]):
            break

    return True


def show_all_contacts(state: AppState) -> bool:
    contacts = state["contacts"]
    return show_contacts_pagination(state, contacts, CONTACTS_PER_PAGE)


def search_contacts(state: AppState) -> bool:
    print_title("Поиск контактов")

    search_input = input("Поиск: ").strip().lower()

    found_contacts = [
        contact for contact in state["contacts"]
        if search_input in contact.name.lower()
        or search_input in contact.phone.lower()
        or search_input in contact.comment.lower()
    ]

    return show_contacts_pagination(state, found_contacts, CONTACTS_PER_PAGE)


def select_contact(state: AppState, visible_contacts: list[Contact]) -> bool:
    contact_id_input = input("ID: ").strip()

    if not contact_id_input.isdigit():
        print_error("ID контакта должен быть положительным числом")
        return True

    contact_id = int(contact_id_input)
    if contact_id <= 0:
        print_error("ID контакта должен быть положительным числом")
        return True

    available_contact_ids = {contact.id for contact in visible_contacts}

    if contact_id not in available_contact_ids:
        print_error(f"Контакт с ID {contact_id} не найден в текущем списке")
        return True

    if contact_id not in state["contacts_id_idx"]:
        print_error(f"Контакт с ID {contact_id} не найден")
        return True

    contact_index = state["contacts_id_idx"][contact_id]
    contact = state["contacts"][contact_index]

    def edit_contact() -> bool:
        old_contact = contact.copy()

        def edit_contact_name() -> bool:
            contact.set_name(input("Имя: ").strip())
            return True

        def edit_contact_phone() -> bool:
            contact.set_phone(input("Телефон: ").strip())
            return True

        def edit_contact_comment() -> bool:
            contact.set_comment(input("Комментарий: ").strip())
            return True

        while True:
            try:
                if not process_actions([
                    {
                        "title": "Редактировать \"Имя\"",
                        "action": edit_contact_name,
                    },
                    {
                        "title": "Редактировать \"Телефон\"",
                        "action": edit_contact_phone,
                    },
                    {
                        "title": "Редактировать \"Комментарий\"",
                        "action": edit_contact_comment,
                    },
                    {
                        "title": "Назад",
                        "action": lambda: False
                    },
                ]):
                    break
            except AppError as err:
                print_error(f"Ошибка редактирования: {str(err)}")

        if old_contact != contact:
            state["has_changes"] = True
            print_success("Контакт отредактирован")

        return True

    def delete_contact() -> bool:
        nonlocal contact_index

        state["contacts"].pop(contact_index)
        if visible_contacts is not state["contacts"]:
            visible_contacts.remove(contact)

        state["has_changes"] = True
        rebuild_contacts_indexes(state)

        print_success("Контакт удален")

        return False

    actions: list[MenuAction] = [
        {
            "title": "Редактировать",
            "action": edit_contact,
        },
        {
            "title": "Удалить",
            "action": delete_contact,
        },
        {
            "title": "Назад",
            "action": lambda: False
        },
    ]

    while True:
        print_title("Выбран контакт:")
        print_contact(contact)

        if not process_actions(actions):
            break

    return True


def add_contact(state: AppState) -> bool:
    print_title("Добавление контакта")

    name = input("Имя: ").strip()
    phone = input("Телефон: ").strip()
    comment = input("Комментарий: ").strip()

    next_contact_id = state["next_contact_id"]

    try:
        contact = Contact(
            id=next_contact_id,
            name=name,
            phone=phone,
            comment=comment,
        )
    except AppError as err:
        print_error(f"Не удалось добавить контакт: {err}")
        return True

    state["contacts"].append(contact)
    state["contacts_id_idx"][next_contact_id] = len(state["contacts"]) - 1
    state["has_changes"] = True
    state["next_contact_id"] += 1

    print_success("Контакт добавлен:")
    print_contact(contact)

    return True


def process_actions(actions: list[MenuAction]) -> bool:
    print_section("Доступные действия")

    for number, action in enumerate(actions, start=1):
        print(f"  {number}. {action['title']}")

    action_number = input(f"\nВыберите действие [1-{len(actions)}]: ").strip()

    if not action_number.isdigit():
        print_error("Необходимо ввести номер действия.")
        return True

    action_index = int(action_number) - 1
    if action_index not in range(0, len(actions)):
        print_error("Такого действия не существует.")
        return True

    try:
        return actions[action_index]["action"]()
    except AppError as err:
        print_error(str(err))
        return True


def exit_app(state: AppState) -> bool:
    if not state["has_changes"]:
        return False

    print_warning("Есть несохраненные изменения")
    is_save = input_yes_no("Сохранить перед выходом?")

    if is_save:
        save_contacts(state)

    return False


def rebuild_contacts_indexes(state: AppState) -> None:
    state["contacts_id_idx"] = {
        contact.id: index
        for index, contact in enumerate(state["contacts"])
    }


def run_app() -> None:
    contacts, contacts_path = load_contacts()

    state = AppState(
        contacts=contacts,
        contacts_path=contacts_path,
        contacts_id_idx={},
        has_changes=False,
        next_contact_id=0,
    )

    rebuild_contacts_indexes(state)
    if len(state["contacts_id_idx"]) != len(contacts):
        raise AppError("Среди контактов найдены дубликаты по ID")

    state["next_contact_id"] = max(state["contacts_id_idx"].keys(), default=0) + 1

    print_title("Телефонная книга")
    print_info(f"Файл контактов: {contacts_path}")
    print_info(f"Загружено контактов: {len(contacts)}")

    actions: list[MenuAction] = [
        {
            "title": "Показать все контакты",
            "action": lambda: show_all_contacts(state),
        },
        {
            "title": "Найти контакт",
            "action": lambda: search_contacts(state),
        },
        {
            "title": "Добавить контакт",
            "action": lambda: add_contact(state),
        },
        {
            "title": "Выбрать контакт",
            "action": lambda: select_contact(state, state["contacts"])
        },
        {
            "title": "Сохранить",
            "action": lambda: save_contacts(state),
        },
        {
            "title": "Выход",
            "action": lambda: exit_app(state),
        },
    ]

    while process_actions(actions):
        pass


if __name__ == '__main__':
    try:
        run_app()
    except AppError as e:
        print_error(str(e))
    except KeyboardInterrupt:
        pass
