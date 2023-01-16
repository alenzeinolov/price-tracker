from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from typing import Sequence
import logging
import os
import re

from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
import boto3
import requests

from data import PriceItem
from data import TargetItem

AWS_REGION = 'eu-central-1'

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
target_item_table = dynamodb.Table('target-items')
price_item_table = dynamodb.Table('price-items')


def get_target_items() -> Sequence[TargetItem]:
    response = target_item_table.scan()
    return [
        TargetItem(
            title=item['title'],
            url=item['url'],
            element=item['element'],
        ) for item in response['Items']
    ]


def get_price_item(title: str) -> Optional[PriceItem]:
    try:
        response = price_item_table.get_item(Key={'title': title})
        data = response['Item']
        return PriceItem(
            title=data['title'],
            price=data['price'],
        )
    except (KeyError, ClientError):
        return None


def create_price_item(title: str, price: Decimal) -> PriceItem:
    dt = datetime.now().isoformat()
    price_item_table.put_item(
        Item={
            'title': title,
            'price': price,
            'created': dt,
            'updated': dt,
        }
    )
    return get_price_item(title)


def update_price_item(title: str, price: Decimal) -> PriceItem:
    price_item_table.update_item(
        Key={'title': title},
        UpdateExpression='SET price = :price, updated = :updated',
        ExpressionAttributeValues={
            ':price': price,
            ':updated': datetime.now().isoformat(),
        },
    )
    return get_price_item(title)


def send_price_message(price_item: PriceItem, prev_price: Decimal) -> None:
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    trend = '\U0001F7E2' if price_item.price > prev_price else '\U0001F534'
    requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': f'{price_item.title} - {price_item.price} {trend}'})


def process_target_item(target_item: TargetItem) -> None:
    response = requests.get(target_item.url, headers=DEFAULT_HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')

    element = soup.find(**target_item.element)

    price = Decimal(''.join(re.findall(r'\d+', element.text)))

    price_item = get_price_item(target_item.title)
    if price_item is None:
        price_item = create_price_item(target_item.title, price)
        send_price_message(price_item, Decimal())
    elif price_item.price != price:
        update_price_item(price_item.title, price)
        send_price_message(price_item, price)


def main():
    for target_item in get_target_items():
        process_target_item(target_item)


def lambda_handler(event, context):
    main()
    return {
        'statusCode': 200,
    }


if __name__ == '__main__':
    main()
