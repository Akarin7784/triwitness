[BUG]description for query paramters can not show in swagger ui
Hi, when I add a description for a schema used in query, it can not show in swagger ui but can show in Redoc
```py
@HELLO.route('/', methods=['GET'])
@api.validate(query=HelloForm)
def hello():
    """
    hello 注释
    :return:
    """
   return 'ok'

class HelloForm(BaseModel):
    """
    hello表单
    """
    user: str # 用户名称
    msg: str = Field(description='msg test', example='aa')
    index: int
    data: HelloGetListForm
    list: List[HelloListForm]
```

![截屏2020-10-12 下午7 54 52](https://user-images.githubusercontent.com/60063723/95743785-de70f480-0cc4-11eb-857b-fffd3d7e9cdd.png)
![截屏2020-10-12 下午7 53 59](https://user-images.githubusercontent.com/60063723/95743805-e5980280-0cc4-11eb-99ae-11e6439bae02.png)
