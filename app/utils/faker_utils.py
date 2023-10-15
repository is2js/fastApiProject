from faker import Faker
from faker.providers import BaseProvider

from app.models import UserStatus, Gender, SnsType, RoleName
from app.utils.auth_utils import hash_password


class UserProvider(BaseProvider):

    def create_user_info(self, **kwargs):
        _faker = self.generator
        # profile = _faker.profile()
        # print(profile)
        # {'job': '여행 및 관광통역 안내원', 'company': '유한회사 서',
        # 'ssn': '130919-1434984', 'residence': '인천광역시 동작구 백제고분가 (영숙이리)',
        # 'current_location': (Decimal('-58.1016835'), Decimal('-118.314709')),
        # 'blood_group': 'B-', 'website': ['https://gimgim.com/', 'http://www.baecoei.org/'],
        # 'username': 'sunog18', 'name': '안정호', 'sex': 'M', 'address': '서울특별시 강서구 논현길 (은정박읍)',
        # 'mail': 'hwangsumin@hotmail.com', 'birthdate': datetime.date(1962, 6, 12)}
        fake_profile = _faker.profile(
            fields=['ssn', 'username', 'name', 'sex', 'mail']
        )
        phone_number = _faker.bothify(text='010-####-####')
        age = _faker.random.randint(16, 70)

        status = _faker.random_element(UserStatus).value
        gender = _faker.random_element(Gender).value
        sns_type = _faker.random_element(SnsType).value

        role_name = _faker.random_element(RoleName).value

        return dict(
            email=fake_profile['mail'],
            hashed_password=hash_password("string"),
            phone_number=phone_number,
            name=fake_profile['name'],
            nickname=fake_profile['username'],
            birthday=fake_profile['ssn'][:6],
            age=age,
            status=status,
            gender=gender,
            sns_type=sns_type,
            role_name=role_name,
        ) | kwargs


my_faker: Faker = Faker(locale='ko_KR')
my_faker.add_provider(UserProvider)

if __name__ == '__main__':
    print(my_faker.create_user_info(status='ACTIVE'))
    # {'email': 'asdf', 'pw': 'string', 'phone_number': '010-3395-0942', 'name': '강건우', 'nickname': 'cunjai', 'birthday': '470210'}
